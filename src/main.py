#!/usr/bin/python3
"""
Invoice Processing and Validation System

This is the main entry point for the invoice processing system. It orchestrates
the extraction of invoice data from images using AI, validates the extracted data
against business rules, and generates detailed validation reports.

Usage:
    python main.py <path_to_invoice_pdf>
    
Example:
    python main.py invoices/invoice_001.pdf
"""

import sys
import json
import os
from pathlib import Path
from typing import Dict, Any

from gemini_client import GeminiClient
from validator import InvoiceValidator
from helper import pdf_to_png_images, are_pdf_pages_blank


class InvoiceProcessor:
    """
    Main processor for invoice extraction and validation workflow.
    
    This class coordinates the entire process of extracting invoice data from images,
    validating the extracted information, and generating comprehensive reports.
    
    Attributes:
        gemini_client (GeminiClient): Client for AI-powered data extraction.
        validator (InvoiceValidator): Validator for invoice data verification.
    """
    
    def __init__(self, api_key: str = None, model_name: str = None):
        """
        Initialize the invoice processor with extraction and validation capabilities.
        
        Args:
            api_key (str, optional): Gemini API key. If None, uses default from GeminiClient.
            model_name (str, optional): Gemini model name. If None, uses default from GeminiClient.
        """
        if api_key and model_name:
            self.gemini_client = GeminiClient(api_key=api_key, model_name=model_name)
        elif api_key:
            self.gemini_client = GeminiClient(api_key=api_key)
        else:
            self.gemini_client = GeminiClient()
        
        self.validator = InvoiceValidator()
    
    def _validate_pdf(self, pdf_path: str):
        """
        Validate the structural integrity of the invoice PDF.

        Rules enforced:
            1. The PDF must contain exactly 1 page.
            2. The first (and only) page must not be blank.

        Args:
            pdf_path (str): Path to the PDF file on disk.

        Raises:
            ValueError: If the PDF has more than one page.
            ValueError: If the first page is blank.
        """
        pages = pdf_to_png_images(pdf_path, dpi=150)

        if len(pages) > 1:
            raise ValueError(
                f"Invalid PDF: the file contains {len(pages)} pages. "
                "Only single-page invoices are accepted."
            )

        blank_flags = are_pdf_pages_blank(pdf_path, dpi=150)
        if blank_flags[0]:
            raise ValueError("Invalid PDF: the first page is blank.")

    def _convert_pdf_to_jpg_tmpfile(self, pdf_path: str) -> str:
        """
        Render the first page of the validated PDF to a JPEG temporary file.

        Args:
            pdf_path (str): Path to the validated single-page PDF.

        Returns:
            str: Absolute path to the created JPEG temporary file.
                 The caller is responsible for deleting this file after use.
        """
        import tempfile
        pages = pdf_to_png_images(pdf_path, dpi=200)
        page_image = pages[0].convert("RGB")  # JPEG requires RGB mode

        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        tmp.close()  # Close so PIL can write on all platforms
        page_image.save(tmp.name, format="JPEG", quality=95)
        return tmp.name

    def extract_data(self, pdf_path: str) -> Dict[str, Any]:
        """
        Validate, convert, and extract structured data from an invoice PDF.

        The PDF is first checked for structural validity (single non-blank
        page), then rendered to a JPEG temporary file which is passed to
        the Gemini client for extraction. The temporary file is cleaned up
        automatically before this method returns.

        Args:
            pdf_path (str): Path to the invoice PDF file.

        Returns:
            dict: Extracted invoice data in structured format.

        Raises:
            FileNotFoundError: If the PDF file does not exist.
            ValueError: If the PDF fails structural validation.
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"Invoice PDF not found at: {pdf_path}")

        # Structural validation (page count + blank check)
        print(f"Validating PDF: {pdf_path}")
        self._validate_pdf(pdf_path)
        print("PDF validation passed.")

        # Convert the single page to a JPEG temp file
        jpg_tmp_path = self._convert_pdf_to_jpg_tmpfile(pdf_path)

        try:
            print(f"Extracting data from: {pdf_path}")
            extracted_data = self.gemini_client.extract_invoice_data(jpg_tmp_path)
            print("Data extraction completed successfully.")
        finally:
            # Always remove the JPEG temp file
            if os.path.exists(jpg_tmp_path):
                os.remove(jpg_tmp_path)

        return extracted_data
    
    def validate_data(self, extracted_data: Dict[str, Any]) -> Dict[str, Dict]:
        """
        Validate extracted invoice data against business rules.
        
        Args:
            extracted_data (dict): Extracted invoice data from the AI model.
        
        Returns:
            dict: Validation results containing errors and passes for each section.
        """
        print("\nValidating extracted data...")
        
        # Validate letter head
        if 'letter_head' in extracted_data:
            self.validator.validate_letter_head(extracted_data['letter_head'])
        
        # Validate tax invoice
        if 'tax_invoice' in extracted_data:
            self.validator.validate_tax_invoice(extracted_data['tax_invoice'])
        
        # Validate bill-to details
        if 'bill_to_details' in extracted_data:
            self.validator.validate_bill_to_details(extracted_data['bill_to_details'])
        
        # Validate invoice details
        if 'invoice_details' in extracted_data:
            self.validator.validate_invoice_details(extracted_data['invoice_details'])
        
        # Validate resource and bill details
        if 'resource_and_bill_details' in extracted_data and 'total_invoice_value' in extracted_data:
            self.validator.validate_resource_and_bill_details(
                extracted_data['resource_and_bill_details'],
                extracted_data['total_invoice_value']
            )
        
        # Validate note
        if 'note' in extracted_data:
            self.validator.validate_note(extracted_data['note'])
        
        # Validate beneficiary details
        if 'beneficiary_details' in extracted_data:
            self.validator.validate_beneficiary_details(extracted_data['beneficiary_details'])
        
        # Validate QR code
        if 'qr_code' in extracted_data:
            self.validator.validate_qr_code(extracted_data['qr_code'])
        
        # Validate digital signature
        if 'digital_signature' in extracted_data:
            self.validator.validate_digital_signature(extracted_data['digital_signature'])
        
        print("Validation completed.")
        
        return self.validator.get_validation_results()
    
    def generate_report(self, extracted_data: Dict[str, Any], 
                       validation_results: Dict[str, Dict],
                       output_path: str = None) -> str:
        """
        Generate a comprehensive report of extraction and validation results.
        
        Args:
            extracted_data (dict): The extracted invoice data.
            validation_results (dict): The validation results containing errors and passes.
            output_path (str, optional): Path to save the report. If None, prints to console.
        
        Returns:
            str: Path to the saved report file, or None if printed to console.
        """
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("INVOICE PROCESSING REPORT")
        report_lines.append("=" * 80)
        report_lines.append("")
        
        # Summary statistics
        error_count = self.validator.get_error_count()
        pass_count = self.validator.get_pass_count()
        total_checks = error_count + pass_count
        
        report_lines.append("SUMMARY")
        report_lines.append("-" * 80)
        report_lines.append(f"Total Validation Checks: {total_checks}")
        report_lines.append(f"Passed: {pass_count}")
        report_lines.append(f"Failed: {error_count}")
        
        if total_checks > 0:
            success_rate = (pass_count / total_checks) * 100
            report_lines.append(f"Success Rate: {success_rate:.2f}%")
        
        report_lines.append("")
        
        # Validation results by section
        report_lines.append("VALIDATION RESULTS BY SECTION")
        report_lines.append("-" * 80)
        
        for section in validation_results['errors'].keys():
            section_errors = validation_results['errors'][section]
            section_passes = validation_results['passes'][section]
            
            report_lines.append(f"\n{section.upper().replace('_', ' ')}")
            report_lines.append("  Passes:")
            if section_passes:
                for pass_msg in section_passes:
                    report_lines.append(f"    ✓ {pass_msg}")
            else:
                report_lines.append("    (None)")
            
            report_lines.append("  Errors:")
            if section_errors:
                for error_msg in section_errors:
                    report_lines.append(f"    ✗ {error_msg}")
            else:
                report_lines.append("    (None)")
        
        report_lines.append("")
        report_lines.append("=" * 80)
        report_lines.append("EXTRACTED DATA")
        report_lines.append("=" * 80)
        report_lines.append("")
        report_lines.append(json.dumps(extracted_data, indent=2, ensure_ascii=False))
        report_lines.append("")
        report_lines.append("=" * 80)
        
        report_text = "\n".join(report_lines)
        
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(report_text)
            print(f"\nReport saved to: {output_path}")
            return output_path
        else:
            print("\n" + report_text)
            return None
    
    def process_invoice(self, pdf_path: str, output_dir: str = None) -> Dict[str, Any]:
        """
        Complete end-to-end processing of an invoice.
        
        Extracts data, validates it, and generates reports.
        
        Args:
            pdf_path (str): Path to the invoice PDF file.
            output_dir (str, optional): Directory to save output files. If None, uses current directory.
        
        Returns:
            dict: Dictionary containing:
                - extracted_data: The extracted invoice data
                - validation_results: The validation results
                - report_path: Path to the generated report (if output_dir specified)
        """
        # Extract data (includes PDF validation + temp JPEG conversion internally)
        extracted_data = self.extract_data(pdf_path)

        # Validate data
        validation_results = self.validate_data(extracted_data)

        # Prepare output directory
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

            # Save extracted data
            base_name = Path(pdf_path).stem
            data_path = os.path.join(output_dir, f"{base_name}_extracted_data.json")
            with open(data_path, 'w', encoding='utf-8') as f:
                json.dump(extracted_data, f, indent=2, ensure_ascii=False)
            print(f"Extracted data saved to: {data_path}")
            
            # Save validation results
            validation_path = os.path.join(output_dir, f"{base_name}_validation_results.json")
            with open(validation_path, 'w', encoding='utf-8') as f:
                json.dump(validation_results, f, indent=2, ensure_ascii=False)
            print(f"Validation results saved to: {validation_path}")
            
            # Generate and save report
            report_path = os.path.join(output_dir, f"{base_name}_report.txt")
            self.generate_report(extracted_data, validation_results, report_path)
        else:
            # Just print the report
            self.generate_report(extracted_data, validation_results)
            report_path = None
        
        return {
            'extracted_data': extracted_data,
            'validation_results': validation_results,
            'report_path': report_path
        }


def main():
    """
    Main entry point for command-line usage.
    
    Processes command-line arguments and runs the invoice processing workflow.
    """
    if len(sys.argv) < 2:
        print("Usage: python main.py <path_to_invoice_image> [output_directory]")
        print("\nExample:")
        print("  python main.py invoices/invoice_001.jpg")
        print("  python main.py invoices/invoice_001.jpg output/")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "output"
    
    try:
        processor = InvoiceProcessor()
        results = processor.process_invoice(pdf_path, output_dir)
        
        # Print summary
        print("\n" + "=" * 80)
        print("PROCESSING COMPLETE")
        print("=" * 80)
        
        if results['validation_results']:
            validator = InvoiceValidator()
            # We need to recreate the validator state for final summary
            # This is a simplification - in production you'd pass the validator instance
            error_count = sum(len(errors) for errors in results['validation_results']['errors'].values())
            pass_count = sum(len(passes) for passes in results['validation_results']['passes'].values())
            
            print(f"Validation Errors: {error_count}")
            print(f"Validation Passes: {pass_count}")
            
            if error_count == 0:
                print("\n✓ All validations passed successfully!")
            else:
                print(f"\n✗ {error_count} validation issue(s) found. Check the report for details.")
        
        print("=" * 80)
        
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred during processing: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()