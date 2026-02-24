#!/usr/bin/python3
"""
Invoice Processing and Validation System

Extracts structured data from an invoice PDF using PyMuPDF, validates it
against business rules, and writes output files to the specified directory.

Usage:
    python main.py <invoice.pdf> [output_dir]

Output files (written to output_dir, default: "output/"):
    <stem>_extracted_data.json      – Raw extracted invoice fields
    <stem>_validation_results.json  – Per-section pass / error lists
    <stem>_validation_summary.txt   – Human-readable validation report
"""

import sys
import json
import os
from pathlib import Path
from typing import Any, Dict

from pdf_client import PyMuPDFClient
from validator import InvoiceValidator
from helper import pdf_to_png_images, are_pdf_pages_blank


# ---------------------------------------------------------------------------
# InvoiceProcessor
# ---------------------------------------------------------------------------

class InvoiceProcessor:
    """
    Coordinates PDF validation, PyMuPDF extraction, data validation, and reporting.
    """

    def __init__(self):
        self.validator = InvoiceValidator()

    # ------------------------------------------------------------------
    # PDF validation
    # ------------------------------------------------------------------

    def _validate_pdf(self, pdf_path: str) -> None:
        """Ensure the PDF is a single, non-blank page."""
        pages = pdf_to_png_images(pdf_path, dpi=150)

        if len(pages) > 1:
            raise ValueError(
                f"Invalid PDF: contains {len(pages)} pages. "
                "Only single-page invoices are accepted."
            )

        blank_flags = are_pdf_pages_blank(pdf_path, dpi=150)
        if blank_flags[0]:
            raise ValueError("Invalid PDF: the first page is blank.")

    # ------------------------------------------------------------------
    # Core steps
    # ------------------------------------------------------------------

    def extract_data(self, pdf_path: str) -> Dict[str, Any]:
        """Validate the PDF, then extract invoice data directly via PyMuPDF."""
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"Invoice PDF not found: {pdf_path}")

        print("[1/3] Validating PDF …")
        self._validate_pdf(pdf_path)
        print("      PDF validation passed.")

        print("[2/3] Extracting data with PyMuPDF …")
        client = PyMuPDFClient(pdf_path)
        data = client.extract_invoice_data()
        print("      Extraction complete.")

        return data

    def validate_data(self, extracted_data: Dict[str, Any]) -> Dict[str, Dict]:
        """Run all section validators and return combined results."""
        print("[3/3] Validating extracted data …")

        # Single-argument validators
        checks = [
            ("letter_head",         self.validator.validate_letter_head),
            ("tax_invoice",         self.validator.validate_tax_invoice),
            ("bill_to_details",     self.validator.validate_bill_to_details),
            ("invoice_details",     self.validator.validate_invoice_details),
            ("note",                self.validator.validate_note),
            ("beneficiary_details", self.validator.validate_beneficiary_details),
            ("qr_code",             self.validator.validate_qr_code),
            ("digital_signature",   self.validator.validate_digital_signature),
        ]

        for key, fn in checks:
            if key in extracted_data:
                fn(extracted_data[key])

        # resource_and_bill_details requires two arguments
        if (
            "resource_and_bill_details" in extracted_data
            and "total_invoice_value" in extracted_data
        ):
            self.validator.validate_resource_and_bill_details(
                extracted_data["resource_and_bill_details"],
                extracted_data["total_invoice_value"],
            )

        print("      Validation complete.")
        return self.validator.get_validation_results()

    # ------------------------------------------------------------------
    # Report generation
    # ------------------------------------------------------------------

    def build_summary(self, validation_results: Dict[str, Dict]) -> str:
        """Return a human-readable validation summary string."""
        errors = validation_results["errors"]
        passes = validation_results["passes"]

        error_count = sum(len(v) for v in errors.values())
        pass_count  = sum(len(v) for v in passes.values())
        total       = error_count + pass_count
        rate        = (pass_count / total * 100) if total else 0.0

        lines = [
            "=" * 70,
            "INVOICE VALIDATION SUMMARY",
            "=" * 70,
            "",
            f"  Total checks : {total}",
            f"  Passed       : {pass_count}",
            f"  Failed       : {error_count}",
            f"  Success rate : {rate:.1f}%",
            "",
            "-" * 70,
            "RESULTS BY SECTION",
            "-" * 70,
        ]

        for section in errors:
            title = section.upper().replace("_", " ")
            section_passes = passes.get(section, [])
            section_errors = errors.get(section, [])

            lines.append(f"\n  {title}")

            if section_passes:
                for msg in section_passes:
                    lines.append(f"    ✓  {msg}")
            if section_errors:
                for msg in section_errors:
                    lines.append(f"    ✗  {msg}")
            if not section_passes and not section_errors:
                lines.append("    –  (no checks run)")

        lines += [
            "",
            "=" * 70,
            "OVERALL: " + (
                "ALL VALIDATIONS PASSED ✓"
                if error_count == 0
                else f"{error_count} ISSUE(S) FOUND ✗"
            ),
            "=" * 70,
        ]

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def process(self, pdf_path: str, output_dir: str = "output") -> Dict[str, Any]:
        """
        End-to-end processing: extract → validate → write output files.

        Returns a dict with keys: extracted_data, validation_results, output_files.
        """
        extracted_data     = self.extract_data(pdf_path)
        validation_results = self.validate_data(extracted_data)

        # Prepare output directory
        os.makedirs(output_dir, exist_ok=True)
        stem = Path(pdf_path).stem

        paths = {
            "extracted_data":     os.path.join(output_dir, f"{stem}_extracted_data.json"),
            "validation_results": os.path.join(output_dir, f"{stem}_validation_results.json"),
            "validation_summary": os.path.join(output_dir, f"{stem}_validation_summary.txt"),
        }

        # Write extracted data
        with open(paths["extracted_data"], "w", encoding="utf-8") as f:
            json.dump(extracted_data, f, indent=2, ensure_ascii=False)

        # Write validation results
        with open(paths["validation_results"], "w", encoding="utf-8") as f:
            json.dump(validation_results, f, indent=2, ensure_ascii=False)

        # Write validation summary
        summary = self.build_summary(validation_results)
        with open(paths["validation_summary"], "w", encoding="utf-8") as f:
            f.write(summary)

        return {
            "extracted_data":     extracted_data,
            "validation_results": validation_results,
            "output_files":       paths,
        }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python main.py <invoice.pdf> [output_dir]")
        print("       output_dir defaults to 'output/'")
        sys.exit(1)

    pdf_path   = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "output"

    try:
        processor = InvoiceProcessor()
        results   = processor.process(pdf_path, output_dir)

        paths = results["output_files"]
        val   = results["validation_results"]
        error_count = sum(len(v) for v in val["errors"].values())
        pass_count  = sum(len(v) for v in val["passes"].values())

        print()
        print("=" * 70)
        print("PROCESSING COMPLETE")
        print("=" * 70)
        print(f"  Passed : {pass_count}")
        print(f"  Failed : {error_count}")
        print()
        print("Output files:")
        for label, path in paths.items():
            print(f"  {label:<22} → {path}")
        print("=" * 70)

        if error_count > 0:
            sys.exit(2)  # non-zero exit so CI pipelines can detect failures

    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()