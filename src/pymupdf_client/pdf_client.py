#!/usr/bin/python3
"""
PyMuPDF Invoice Extractor

Extracts structured data from invoice PDFs using PyMuPDF (fitz),
producing output in the same schema as the GeminiClient.
"""

import re
import json
import fitz  # PyMuPDF


class PyMuPDFClient:
    """
    A client for extracting structured invoice data from PDF files using PyMuPDF.
    Produces output matching the schema defined in GeminiClient._get_response_schema().
    """

    def __init__(self, pdf_path: str):
        """
        Initialize the extractor with the path to the invoice PDF.

        Args:
            pdf_path (str): Path to the invoice PDF file.
        """
        self.pdf_path = pdf_path
        self.doc = fitz.open(pdf_path)
        self.text = self._extract_text()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_text(self) -> str:
        """Extract and return all text from the PDF as a single string."""
        return "\n".join(page.get_text() for page in self.doc)

    def _find(self, pattern: str, default: str = "") -> str:
        """
        Search for a regex pattern in the extracted text.

        Args:
            pattern (str): Regex pattern with one capturing group.
            default (str): Value to return when no match is found.

        Returns:
            str: Stripped match or default.
        """
        match = re.search(pattern, self.text, re.IGNORECASE | re.DOTALL)
        return match.group(1).strip() if match else default

    def _has_image(self) -> bool:
        """Return True if the PDF contains at least one embedded image."""
        for page in self.doc:
            if page.get_images(full=True):
                return True
        return False

    # ------------------------------------------------------------------
    # Section extractors
    # ------------------------------------------------------------------

    def _extract_letter_head(self) -> dict:
        return {
            "company_name": self._find(r"Authorised Signatory\n(Genius HRTech Limited)"),
            "former_company_name": self._find(r"(\(Formerly known as[^\)]+\))"),
            "address": re.sub(
                r"\s*\n\s*", " ",
                self._find(r"(Synthesis Business Park\s+Tower[^\n]+\n[^\n]+?\.)\s*CIN No")
            ).strip(),
            "cin": self._find(r"CIN No[:\s]*([A-Z0-9]+)"),
            "gstin": self._find(r"GST NO[:\s]*([A-Z0-9]+)"),
            "phone": self._find(r"Ph[:\s]*([\d\-/]+)"),
            "email": self._find(r"Email[:\s]*([\w\.\-]+@[\w\.\-]+)"),
            "website": self._find(r"Web[:\s]*(www\.[\w\.\-/]+)"),
        }

    def _extract_tax_invoice(self) -> dict:
        # The PAN/TAN under TAX INVOICE heading belong to the supplier
        pan = self._find(r"PAN NO\s*[:\s]*([A-Z]{5}\d{4}[A-Z])")
        tan = self._find(r"TAN NO\s*[:\s]*([A-Z]{4}\d{5}[A-Z])")
        return {
            "pan_no": pan,
            "tan_no": tan,
        }

    def _extract_bill_to_details(self) -> dict:
        # Isolate the bill-to block (between "Bill To:-" and "Sl.")
        # so that PAN/TAN lookups don't bleed into the supplier's values above
        block_match = re.search(
            r"Bill To:-\s*(.*?)(?=Sl\.)", self.text, re.IGNORECASE | re.DOTALL
        )
        block = block_match.group(1) if block_match else ""

        def find_in_block(pattern, default=""):
            m = re.search(pattern, block, re.IGNORECASE | re.DOTALL)
            return m.group(1).strip() if m else default

        # First line of the block = company name
        company = find_in_block(r"^([^\n]+)")

        # Address = everything from the second line up to the GSTIN line
        address_match = re.search(
            r"^[^\n]+\n(.*?)(?=GSTIN)", block, re.IGNORECASE | re.DOTALL
        )
        address = ""
        if address_match:
            address = re.sub(r"\s*\n\s*", " ", address_match.group(1)).strip()

        return {
            "company_name": company,
            "address": address,
            "gstin": find_in_block(r"GSTIN\s*[:\s]*([A-Z0-9]+)"),
            # Pan No / Tan No scoped to the bill-to block (not the supplier block above)
            "pan_no": find_in_block(r"Pan No\s*[:\s]*([A-Z]{5}\d{4}[A-Z])"),
            "tan_no": find_in_block(r"Tan No\s*[:\s]*([A-Z]{4}\d{5}[A-Z])"),
            "place_of_supply": find_in_block(r"Place of Supply[:\s]*([A-Z\-0-9]+)"),
            "irn_no": find_in_block(r"IRN No[.\s]*([a-f0-9]{64})"),
        }

    def _extract_invoice_details(self) -> dict:
        return {
            "date": self._find(r"Date[:\s]*([\d]+\s+\w+\s*\d{4})"),
            "invoice_no": self._find(r"Invoice[:\s]*([A-Z]+/[A-Z0-9]+/\d+)"),
            "service_month": self._find(r"Service Month\s*[:\s]*([^\n]+)"),
            "lower_tds_cert_no": self._find(r"LOWER TDS CERT\.?\s*No\.?\s*[:\s]*([A-Z0-9]+)"),
        }

    def _extract_resource_and_bill_details(self) -> list:
        """
        Parse line-item rows from the table block.

        Two observed PyMuPDF layouts for the same invoice format:

        Layout A (bill_rate == taxable_value, full month):
            1
            SHAILENDRA KUSHWAH
            998513
            8000112642 51980.00     ← po_no + bill_rate share a line
            ERCSIN01233612
            51980.00
            0.00 / 0.00 / 9356.40 / 61336.40

        Layout B (bill_rate != taxable_value, partial month):
            1
            PRASHANT KUMAR
            998513
            8000111210              ← po_no alone
            52189.00                ← bill_rate alone
            ERCSMI00239725 1739.63  ← inv_code + taxable_value share a line
            0.00 / 0.00 / 313.13 / 2052.76

        Strategy: scan all lines after hsn_sac using type-based recognition,
        never relying on fixed line positions.
        """
        table_block_match = re.search(
            r"Total\s+INR\s*\n(.*?)Total\s+Invoice\s*Value",
            self.text, re.IGNORECASE | re.DOTALL
        )
        if not table_block_match:
            return []

        block = table_block_match.group(1).strip()
        rows = []

        float_re   = re.compile(r"^\d[\d,]*\.\d{2}$")
        int6_re    = re.compile(r"^\d{6}$")
        int10_re   = re.compile(r"^\d{10}$")
        invcode_re = re.compile(r"^[A-Z]{3,}[A-Z0-9]+$")

        # Split records on lines that are a standalone serial number (1–3 digits)
        record_splits = re.split(r"(?=^\d{1,3}\n)", block, flags=re.MULTILINE)

        for record in record_splits:
            record = record.strip()
            if not record:
                continue

            lines = [l.strip() for l in record.splitlines() if l.strip()]
            if len(lines) < 2:
                continue

            # Line 0: sl_no — must be 1–3 digit integer
            if not re.fullmatch(r"\d{1,3}", lines[0]):
                continue
            sl_no = lines[0]

            # Line 1: resource_name — all-caps words
            resource_name = lines[1] if re.fullmatch(r"[A-Z][A-Z\s]+", lines[1]) else ""

            # Line 2: hsn_sac — exactly 6 digits
            hsn_sac = lines[2] if len(lines) > 2 and int6_re.fullmatch(lines[2]) else ""

            # --- Scan remaining lines with type-based recognition ---
            po_no = bill_rate = inv_code = ""
            taxable = cgst = sgst = igst = total = ""
            trailing_floats = []  # cgst, sgst, igst, total (always standalone)

            i = 3
            while i < len(lines):
                line = lines[i]
                parts = line.split()

                # Pattern: "8000112642 51980.00" → po_no + bill_rate on one line (Layout A)
                if (len(parts) == 2
                        and int10_re.fullmatch(parts[0])
                        and float_re.fullmatch(parts[1])
                        and not po_no):
                    po_no, bill_rate = parts[0], parts[1]

                # Pattern: standalone 10-digit int → po_no alone (Layout B)
                elif int10_re.fullmatch(line) and not po_no:
                    po_no = line

                # Pattern: standalone float immediately after po_no, before inv_code → bill_rate (Layout B)
                elif float_re.fullmatch(line) and po_no and not bill_rate and not inv_code:
                    bill_rate = line

                # Pattern: "ERCSMI00239725 1739.63" → inv_code + taxable on one line (Layout B)
                elif (len(parts) == 2
                        and invcode_re.fullmatch(parts[0])
                        and float_re.fullmatch(parts[1])
                        and not inv_code):
                    inv_code, taxable = parts[0], parts[1]

                # Pattern: standalone invoice code (Layout A)
                elif invcode_re.fullmatch(line) and not inv_code:
                    inv_code = line

                # Pattern: standalone float after inv_code → taxable then cgst/sgst/igst/total
                elif float_re.fullmatch(line) and inv_code:
                    if not taxable:
                        taxable = line
                    else:
                        trailing_floats.append(line)

                i += 1

            cgst  = trailing_floats[0] if len(trailing_floats) > 0 else ""
            sgst  = trailing_floats[1] if len(trailing_floats) > 1 else ""
            igst  = trailing_floats[2] if len(trailing_floats) > 2 else ""
            total = trailing_floats[3] if len(trailing_floats) > 3 else ""

            rows.append({
                "sl_no": sl_no,
                "resource_name": resource_name,
                "hsn_sac": hsn_sac,
                "po_no": po_no,
                "bill_rate": bill_rate,
                "ericsson_invoice_code": inv_code,
                "taxable_value": taxable,
                "cgst": cgst,
                "sgst": sgst,
                "igst": igst,
                "total_inr": total,
            })

        return rows

    def _extract_total_invoice_value(self) -> dict:
        # The totals line: Total Invoice Value <taxable> <cgst> <sgst> <igst> <total>
        m = re.search(
            r"Total Invoice\s*Value\s+"
            r"([\d,]+\.\d{2})\s+"   # taxable_value
            r"([\d,]+\.\d{2})\s+"   # cgst
            r"([\d,]+\.\d{2})\s+"   # sgst
            r"([\d,]+\.\d{2})\s+"   # igst
            r"([\d,]+\.\d{2})",     # total_inr
            self.text, re.IGNORECASE
        )
        in_words = self._find(
            r"Total Invoice\s*Value\s*\(\s*In\s*Words\s*\)[:\s]*([^\n]+)"
        )

        if m:
            return {
                "taxable_value": m.group(1),
                "cgst": m.group(2),
                "sgst": m.group(3),
                "igst": m.group(4),
                "total_inr": m.group(5),
                "in_words": in_words,
            }
        return {
            "taxable_value": "", "cgst": "", "sgst": "",
            "igst": "", "total_inr": "", "in_words": in_words,
        }

    def _extract_note(self) -> dict:
        """
        Extract NOTE points 1, 2, and the post script (GST contact line).
        """
        note_block = self._find(r"NOTE:\s*(.*?)(?=Bank details)", )
        note_1 = note_2 = post_script = ""

        if note_block:
            # Point 1 — starts with "1."
            m1 = re.search(r"1\.\s*(.*?)(?=2\.)", note_block, re.DOTALL)
            if m1:
                note_1 = re.sub(r"\s+", " ", m1.group(1)).strip()

            # Point 2 — starts with "2." up to the GST contact line
            m2 = re.search(r"2\.\s*(.*?)(?=For any kind|$)", note_block, re.DOTALL)
            if m2:
                note_2 = re.sub(r"\s+", " ", m2.group(1)).strip()

            # Post script — the GST contact line
            mps = re.search(r"(For any kind of GST[^\n]+)", note_block)
            if mps:
                post_script = mps.group(1).strip()

        return {"1": note_1, "2": note_2, "post_script": post_script}

    def _extract_beneficiary_details(self) -> dict:
        return {
            "beneficiary_name": self._find(
                r"Beneficiary Name\s*[:\s]*([^\n]+(?:Limited)[^\n]*)"
            ),
            "bank_name": self._find(r"Bank\s*Name\s*[:\s]*([^\n]+)"),
            "address": self._find(r"Address\s*[:\s]*([\d/A-Z\s]+ROAD)", ),
            "reverse_charge": self._find(r"Reverse\s*Charge\s*[:\s]*(\w+)"),
            "account_no": self._find(r"Account\s*Number\s*[:\s]*(\d+)"),
            "ifsc_code": self._find(r"IFSC\s*Code\s*[:\s]*([A-Z0-9]+)"),
            "micr_code": self._find(r"MICR\s*Code\s*[:\s]*(\d+)"),
            "country": self._find(r"Country\s*[:\s]*(\w+)"),
            "authorised_signatory": self._find(r"Authorised Signatory\s*:\s*([^\n]+)"),
        }

    def _extract_qr_code(self) -> str:
        """
        Detect QR code presence by checking for embedded images in the PDF.
        A more robust approach is to check image count; the invoice has a logo + QR.
        """
        image_count = sum(len(page.get_images(full=True)) for page in self.doc)
        # Invoice has logo (1) + QR code (1) + digital sig (1) = typically 3+
        return "True" if image_count >= 2 else "False"

    def _extract_digital_signature(self) -> str:
        """
        Detect digital signature by looking for signature-related keywords in text.
        """
        sig_keywords = ["digitally signed", "signature not verified", "digital signature"]
        text_lower = self.text.lower()
        return "True" if any(kw in text_lower for kw in sig_keywords) else "False"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract_invoice_data(self) -> dict:
        """
        Extract all invoice fields and return them as a structured dict
        matching the GeminiClient response schema.

        Returns:
            dict: Fully populated invoice data dictionary.
        """
        return {
            "letter_head": self._extract_letter_head(),
            "tax_invoice": self._extract_tax_invoice(),
            "bill_to_details": self._extract_bill_to_details(),
            "invoice_details": self._extract_invoice_details(),
            "resource_and_bill_details": self._extract_resource_and_bill_details(),
            "total_invoice_value": self._extract_total_invoice_value(),
            "arn_for_lut": self._find(r"ARN[^\n]*[:\s]*([^\n]+)"),
            "supply": self._find(r"(?<!Place of )(?<!Place Of )Supply\s*:\s*([^\n]+)"),
            "igst_foregone": self._find(r"IGST\s*Foregone\s*[:\s]*([^\n]+)"),
            "note": self._extract_note(),
            "beneficiary_details": self._extract_beneficiary_details(),
            "qr_code": self._extract_qr_code(),
            "digital_signature": self._extract_digital_signature(),
        }


def pymupdf_client(pdf_path: str) -> dict:
    """
    Convenience wrapper — mirrors the gemini_client() function signature.

    Args:
        pdf_path (str): Path to the invoice PDF.

    Returns:
        dict: Extracted invoice data in the GeminiClient schema.
    """
    client = PyMuPDFClient(pdf_path)
    return client.extract_invoice_data()


# ------------------------------------------------------------------
# CLI entry point
# ------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python pymupdf_client.py <path_to_invoice.pdf>")
        sys.exit(1)

    result = pymupdf_client(sys.argv[1])
    print(json.dumps(result, indent=2, ensure_ascii=False))