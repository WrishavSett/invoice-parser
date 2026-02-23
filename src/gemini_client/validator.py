"""
Invoice Validator Module

This module provides comprehensive validation for invoice data extracted from images.
It validates various sections including letter head, tax details, billing information,
resource details, notes, beneficiary information, and digital artifacts.
"""

import re
from typing import Dict, List

from helper import is_value_present, number_to_words_inr


class ValidationConstants:
    """
    Constants used for invoice validation including regex patterns and expected values.
    """
    
    # Regular expression patterns
    GSTIN_PATTERN = r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$'
    PAN_PATTERN = r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$'
    TAN_PATTERN = r'^[A-Z]{4}[0-9]{5}[A-Z]{1}$'
    IRN_PATTERN = r'^[a-fA-F0-9]{64}$'
    DATE_PATTERN = r'^(0[1-9]|[12][0-9]|3[01])\s(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s\d{4}$'
    
    # Hardcoded expected values
    EMAIL_ID = "enquiry@geniushrtech.com"
    WEBSITE = "www.geniushrtech.com"
    TAX_INVOICE_TEXT = "TAX INVOICE"
    BENEFICIARY_TEXT = "Bank details for money transfer as follows"
    NOTE_TEXT = """1. Please check the calculation/attendance/amount of the bill and inform us within 48 hours in case of any discrepancy, to avoid last minute rush. Any changes reported after 48 hours will be adjusted along with the next month's bill.
2. As per the IT rule u/s 194JB, if our Invoices value in a year is more than Rs. 50,000/-, then you may deduct TDS @ 0.50% Excluding GST
For any kind of GST related query, please contact at : gstsupport@geniushrtech.com
"""
    
    # Expected text values
    COMPANY_NAME = "Genius HRTech Limited"
    FORMER_NAME = "(Formerly known as Genius Consultants Limited)"


class InvoiceValidator:
    """
    A comprehensive validator for invoice data with section-wise validation capabilities.
    
    This class validates all sections of an invoice including letter head, tax information,
    billing details, resource information, notes, and beneficiary details. It tracks both
    validation errors and passes for detailed reporting.
    
    Attributes:
        errors (dict): Dictionary tracking validation errors by section.
        passes (dict): Dictionary tracking validation passes by section.
        constants (ValidationConstants): Validation constants and patterns.
    """
    
    def __init__(self):
        """
        Initialize the invoice validator with empty error and pass tracking.
        """
        self.errors = {
            "letter_head": [],
            "tax_invoice": [],
            "bill_to": [],
            "invoice": [],
            "resource_and_bill": [],
            "note": [],
            "beneficiary": [],
            "qr_code": [],
            "digital_signature": []
        }
        
        self.passes = {
            "letter_head": [],
            "tax_invoice": [],
            "bill_to": [],
            "invoice": [],
            "resource_and_bill": [],
            "note": [],
            "beneficiary": [],
            "qr_code": [],
            "digital_signature": []
        }
        
        self.constants = ValidationConstants()
    
    def validate_letter_head(self, letter_head: dict):
        """
        Validate the letter head section of the invoice.
        
        Validates company name, former company name, GSTIN, email, and website
        against expected values and formats.
        
        Args:
            letter_head (dict): Dictionary containing letter head information with keys:
                - company_name (str): Current company name
                - former_company_name (str): Previous company name
                - gstin (str): GST Identification Number
                - email (str): Company email address
                - website (str): Company website URL
        """
        if 'company_name' not in letter_head:
            self.errors["letter_head"].append("Company name key is missing in letter head.")
        elif 'company_name' in letter_head:
            if is_value_present(letter_head['company_name']) != True:
                self.errors["letter_head"].append("Company name value is missing or empty in letter head.")
            elif is_value_present(letter_head['company_name']) == True:
                if letter_head['company_name'] != self.constants.COMPANY_NAME:
                    self.errors["letter_head"].append("Company name does not match the expected company name.")
                elif letter_head['company_name'] == self.constants.COMPANY_NAME:
                    self.passes["letter_head"].append("Company name is present and matches the expected value.")

        if 'former_company_name' not in letter_head:
            self.errors["letter_head"].append("Former company name key is missing in letter head.")
        elif 'former_company_name' in letter_head:
            if is_value_present(letter_head['former_company_name']) != True:
                self.errors["letter_head"].append("Former company name value is missing or empty in letter head.")
            elif is_value_present(letter_head['former_company_name']) == True:
                if '\n' in letter_head['former_company_name']:
                    self.errors["letter_head"].append("Former company name contains invalid newline characters.")
                elif '\n' not in letter_head['former_company_name']:
                    if letter_head['former_company_name'] != self.constants.FORMER_NAME:
                        self.errors["letter_head"].append("Former company name does not match the expected value.")
                    elif letter_head['former_company_name'] == self.constants.FORMER_NAME:
                        self.passes["letter_head"].append("Former company name is present and matches the expected value.")

        if 'gstin' not in letter_head:
            self.errors["letter_head"].append("GSTIN key is missing in letter head.")
        elif 'gstin' in letter_head:
            if is_value_present(letter_head['gstin']) != True:
                self.errors["letter_head"].append("GSTIN value is missing or empty in letter head.")
            elif is_value_present(letter_head['gstin']) == True:
                if not re.match(self.constants.GSTIN_PATTERN, letter_head['gstin']):
                    self.errors["letter_head"].append("GSTIN format is invalid in letter head.")
                elif re.match(self.constants.GSTIN_PATTERN, letter_head['gstin']):
                    self.passes["letter_head"].append("GSTIN is present and format is valid.")

        if 'email' not in letter_head:
            self.errors["letter_head"].append("Email ID key is missing in letter head.")
        elif 'email' in letter_head:
            if is_value_present(letter_head['email']) != True:
                self.errors["letter_head"].append("Email ID value is missing or empty in letter head.")
            elif is_value_present(letter_head['email']) == True:
                if letter_head['email'] != self.constants.EMAIL_ID:
                    self.errors["letter_head"].append("Email ID does not match the expected email address.")
                elif letter_head['email'] == self.constants.EMAIL_ID:
                    self.passes["letter_head"].append("Email ID is present and matches the expected value.")

        if 'website' not in letter_head:
            self.errors["letter_head"].append("Website key is missing in letter head.")
        elif 'website' in letter_head:
            if is_value_present(letter_head['website']) != True:
                self.errors["letter_head"].append("Website value is missing or empty in letter head.")
            elif is_value_present(letter_head['website']) == True:
                if letter_head['website'] != self.constants.WEBSITE:
                    self.errors["letter_head"].append("Website does not match the expected URL.")
                elif letter_head['website'] == self.constants.WEBSITE:
                    self.passes["letter_head"].append("Website is present and matches the expected value.")
    
    def validate_tax_invoice(self, tax_invoice: dict):
        """
        Validate the tax invoice section.
        
        Validates PAN and TAN numbers against standard format patterns.
        
        Args:
            tax_invoice (dict): Dictionary containing tax information with keys:
                - pan_no (str): Permanent Account Number
                - tan_no (str): Tax Deduction and Collection Account Number
        """
        if 'pan_no' not in tax_invoice:
            self.errors["tax_invoice"].append("PAN number key is missing in tax invoice.")
        elif 'pan_no' in tax_invoice:
            if is_value_present(tax_invoice['pan_no']) != True:
                self.errors["tax_invoice"].append("PAN number value is missing or empty in tax invoice.")
            elif is_value_present(tax_invoice['pan_no']) == True:
                if not re.match(self.constants.PAN_PATTERN, tax_invoice['pan_no']):
                    self.errors["tax_invoice"].append("PAN number format is invalid.")
                elif re.match(self.constants.PAN_PATTERN, tax_invoice['pan_no']):
                    self.passes["tax_invoice"].append("PAN number is present and format is valid.")

        if 'tan_no' not in tax_invoice:
            self.errors["tax_invoice"].append("TAN number key is missing in tax invoice.")
        elif 'tan_no' in tax_invoice:
            if is_value_present(tax_invoice['tan_no']) != True:
                self.errors["tax_invoice"].append("TAN number value is missing or empty in tax invoice.")
            elif is_value_present(tax_invoice['tan_no']) == True:
                if not re.match(self.constants.TAN_PATTERN, tax_invoice['tan_no']):
                    self.errors["tax_invoice"].append("TAN number format is invalid.")
                elif re.match(self.constants.TAN_PATTERN, tax_invoice['tan_no']):
                    self.passes["tax_invoice"].append("TAN number is present and format is valid.")

    def validate_bill_to_details(self, bill_to: dict):
        """
        Validate the bill-to details section.
        
        Validates customer information including company name, address, GSTIN,
        PAN, TAN, place of supply, and IRN number.
        
        Args:
            bill_to (dict): Dictionary containing billing information with keys:
                - company_name (str): Customer company name
                - address (str): Customer address
                - gstin (str): Customer GST number
                - pan_no (str): Customer PAN number
                - tan_no (str): Customer TAN number
                - place_of_supply (str): Place of supply location
                - irn_no (str): Invoice Reference Number (64-character hex)
        """
        if 'company_name' not in bill_to:
            self.errors["bill_to"].append("Company name key is missing in bill-to details.")
        elif 'company_name' in bill_to:
            if is_value_present(bill_to['company_name']) != True:
                self.errors["bill_to"].append("Company name value is missing or empty in bill-to details.")
            elif is_value_present(bill_to['company_name']) == True:
                self.passes["bill_to"].append("Company name is present in bill-to details.")

        if 'address' not in bill_to:
            self.errors["bill_to"].append("Address key is missing in bill-to details.")
        elif 'address' in bill_to:
            if is_value_present(bill_to['address']) != True:
                self.errors["bill_to"].append("Address value is missing or empty in bill-to details.")
            elif is_value_present(bill_to['address']) == True:
                self.passes["bill_to"].append("Address is present in bill-to details.")

        if 'gstin' not in bill_to:
            self.errors["bill_to"].append("GSTIN key is missing in bill-to details.")
        elif 'gstin' in bill_to:
            if is_value_present(bill_to['gstin']) != True:
                self.errors["bill_to"].append("GSTIN value is missing or empty in bill-to details.")
            elif is_value_present(bill_to['gstin']) == True:
                if not re.match(self.constants.GSTIN_PATTERN, bill_to['gstin']):
                    self.errors["bill_to"].append("GSTIN format is invalid in bill-to details.")
                elif re.match(self.constants.GSTIN_PATTERN, bill_to['gstin']):
                    self.passes["bill_to"].append("GSTIN is present and format is valid in bill-to details.")

        if 'pan_no' not in bill_to:
            self.errors["bill_to"].append("PAN number key is missing in bill-to details.")
        elif 'pan_no' in bill_to:
            if is_value_present(bill_to['pan_no']) != True:
                self.errors["bill_to"].append("PAN number value is missing or empty in bill-to details.")
            elif is_value_present(bill_to['pan_no']) == True:
                if not re.match(self.constants.PAN_PATTERN, bill_to['pan_no']):
                    self.errors["bill_to"].append("PAN number format is invalid in bill-to details.")
                elif re.match(self.constants.PAN_PATTERN, bill_to['pan_no']):
                    self.passes["bill_to"].append("PAN number is present and format is valid in bill-to details.")

        if 'tan_no' not in bill_to:
            self.errors["bill_to"].append("TAN number key is missing in bill-to details.")
        elif 'tan_no' in bill_to:
            if is_value_present(bill_to['tan_no']) != True:
                self.errors["bill_to"].append("TAN number value is missing or empty in bill-to details.")
            elif is_value_present(bill_to['tan_no']) == True:
                if not re.match(self.constants.TAN_PATTERN, bill_to['tan_no']):
                    self.errors["bill_to"].append("TAN number format is invalid in bill-to details.")
                elif re.match(self.constants.TAN_PATTERN, bill_to['tan_no']):
                    self.passes["bill_to"].append("TAN number is present and format is valid in bill-to details.")

        if 'place_of_supply' not in bill_to:
            self.errors["bill_to"].append("Place of supply key is missing in bill-to details.")
        elif 'place_of_supply' in bill_to:
            if is_value_present(bill_to['place_of_supply']) != True:
                self.errors["bill_to"].append("Place of supply value is missing or empty in bill-to details.")
            elif is_value_present(bill_to['place_of_supply']) == True:
                self.passes["bill_to"].append("Place of supply is present in bill-to details.")

        if 'irn_no' not in bill_to:
            self.errors["bill_to"].append("IRN number key is missing in bill-to details.")
        elif 'irn_no' in bill_to:
            if is_value_present(bill_to['irn_no']) != True:
                self.errors["bill_to"].append("IRN number value is missing or empty in bill-to details.")
            elif is_value_present(bill_to['irn_no']) == True:
                if not re.match(self.constants.IRN_PATTERN, bill_to['irn_no']):
                    self.errors["bill_to"].append("IRN number format is invalid in bill-to details.")
                elif re.match(self.constants.IRN_PATTERN, bill_to['irn_no']):
                    self.passes["bill_to"].append("IRN number is present and format is valid in bill-to details.")

    def validate_invoice_details(self, invoice: dict):
        """
        Validate the invoice details section.
        
        Validates invoice metadata including date, invoice number, service month,
        and TDS certificate number.
        
        Args:
            invoice (dict): Dictionary containing invoice metadata with keys:
                - date (str): Invoice date in format "DD Mon YYYY"
                - invoice_no (str): Unique invoice number
                - service_month (str): Month for which service was provided
                - lower_tds_cert_no (str): Lower TDS certificate number (optional)
        """
        if 'date' not in invoice:
            self.errors["invoice"].append("Date key is missing in invoice details.")
        elif 'date' in invoice:
            if is_value_present(invoice['date']) != True:
                self.errors["invoice"].append("Date value is missing or empty in invoice details.")
            elif is_value_present(invoice['date']) == True:
                if not re.match(self.constants.DATE_PATTERN, invoice['date']):
                    self.errors["invoice"].append("Date format is invalid in invoice details.")
                elif re.match(self.constants.DATE_PATTERN, invoice['date']):
                    self.passes["invoice"].append("Date is present and format is valid in invoice details.")

        if 'invoice_no' not in invoice:
            self.errors["invoice"].append("Invoice number key is missing in invoice details.")
        elif 'invoice_no' in invoice:
            if is_value_present(invoice['invoice_no']) != True:
                self.errors["invoice"].append("Invoice number value is missing or empty in invoice details.")
            elif is_value_present(invoice['invoice_no']) == True:
                self.passes["invoice"].append("Invoice number is present in invoice details.")

        if 'service_month' not in invoice:
            self.errors["invoice"].append("Service month key is missing in invoice details.")
        elif 'service_month' in invoice:
            if is_value_present(invoice['service_month']) != True:
                self.errors["invoice"].append("Service month value is missing or empty in invoice details.")
            elif is_value_present(invoice['service_month']) == True:
                self.passes["invoice"].append("Service month is present in invoice details.")

        if 'lower_tds_cert_no' not in invoice:
            self.errors["invoice"].append("Lower TDS certificate number key is missing in invoice details.")
        elif 'lower_tds_cert_no' in invoice:
            self.passes["invoice"].append("Lower TDS certificate number key is present in invoice details.")

    def validate_resource_and_bill_details(self, resource_and_bill: list, total_invoice_value: dict):
        """
        Validate resource and billing details including line items and totals.
        
        Validates individual line items for completeness, performs arithmetic validation
        on tax calculations, and verifies total amounts match across line items and
        invoice totals. Also validates the word representation of the total amount.
        
        Args:
            resource_and_bill (list): List of dictionaries, each containing:
                - sl_no (str): Serial number
                - resource_name (str): Resource/employee name
                - hsn_sac (str): HSN/SAC code
                - po_no (str): Purchase order number
                - bill_rate (str): Billing rate
                - ericsson_invoice_code (str): Ericsson invoice code
                - taxable_value (str): Base taxable amount
                - cgst (str): Central GST amount
                - sgst (str): State GST amount
                - igst (str): Integrated GST amount
                - total_inr (str): Line item total in INR
            
            total_invoice_value (dict): Dictionary containing invoice totals:
                - total_inr (str): Total invoice amount
                - in_words (str): Amount in words
        """
        taxable_value = 0.00
        cgst = 0.00
        sgst = 0.00
        igst = 0.00
        total_inr = 0.00

        cgst_percent = 9.0
        sgst_percent = 9.0
        igst_percent = 18.0

        if len(resource_and_bill) == 0:
            self.errors["resource_and_bill"].append("Resource and bill details list has NO line items.")
        else:
            self.passes["resource_and_bill"].append("Resource and bill details list has line items.")

            for item in resource_and_bill:
                if 'sl_no' not in item:
                    self.errors["resource_and_bill"].append("Serial number key is missing.")
                elif 'sl_no' in item:
                    if is_value_present(item['sl_no']) != True:
                        self.errors["resource_and_bill"].append("Serial number value is missing or empty.")
                    elif is_value_present(item['sl_no']) == True:
                        self.passes["resource_and_bill"].append("Serial number is present.")

                if 'resource_name' not in item:
                    self.errors["resource_and_bill"].append("Resource name key is missing.")
                elif 'resource_name' in item:
                    if is_value_present(item['resource_name']) != True:
                        self.errors["resource_and_bill"].append("Resource name value is missing or empty.")
                    elif is_value_present(item['resource_name']) == True:
                        self.passes["resource_and_bill"].append("Resource name is present.")

                if 'hsn_sac' not in item:
                    self.errors["resource_and_bill"].append("HSN/SAC key is missing.")
                elif 'hsn_sac' in item:
                    if is_value_present(item['hsn_sac']) != True:
                        self.errors["resource_and_bill"].append("HSN/SAC value is missing or empty.")
                    elif is_value_present(item['hsn_sac']) == True:
                        self.passes["resource_and_bill"].append("HSN/SAC is present.")

                if 'po_no' not in item:
                    self.errors["resource_and_bill"].append("PO number key is missing.")
                elif 'po_no' in item:
                    if is_value_present(item['po_no']) != True:
                        self.errors["resource_and_bill"].append("PO number value is missing or empty.")
                    elif is_value_present(item['po_no']) == True:
                        self.passes["resource_and_bill"].append("PO number is present.")

                if 'bill_rate' not in item:
                    self.errors["resource_and_bill"].append("Bill rate key is missing.")
                elif 'bill_rate' in item:
                    if is_value_present(item['bill_rate']) != True:
                        self.errors["resource_and_bill"].append("Bill rate value is missing or empty.")
                    elif is_value_present(item['bill_rate']) == True:
                        self.passes["resource_and_bill"].append("Bill rate is present.")

                if 'ericsson_invoice_code' not in item:
                    self.errors["resource_and_bill"].append("Ericsson invoice code key is missing.")
                elif 'ericsson_invoice_code' in item:
                    if is_value_present(item['ericsson_invoice_code']) != True:
                        self.errors["resource_and_bill"].append("Ericsson invoice code value is missing or empty.")
                    elif is_value_present(item['ericsson_invoice_code']) == True:
                        self.passes["resource_and_bill"].append("Ericsson invoice code is present.")

                if 'taxable_value' not in item:
                    self.errors["resource_and_bill"].append("Taxable value key is missing.")
                elif 'taxable_value' in item:
                    if item['taxable_value'] == '':
                        taxable_value = 0.00
                    else:
                        taxable_value = float(item['taxable_value'])
                    self.passes["resource_and_bill"].append("Taxable value is present.")

                if 'cgst' not in item:
                    self.errors["resource_and_bill"].append("CGST key is missing.")
                elif 'cgst' in item:
                    if item['cgst'] == '':
                        cgst = 0.00
                    else:
                        cgst = float(item['cgst'])
                    self.passes["resource_and_bill"].append("CGST is present.")

                if 'sgst' not in item:
                    self.errors["resource_and_bill"].append("SGST key is missing.")
                elif 'sgst' in item:
                    if item['sgst'] == '':
                        sgst = 0.00
                    else:
                        sgst = float(item['sgst'])
                    self.passes["resource_and_bill"].append("SGST is present.")

                if 'igst' not in item:
                    self.errors["resource_and_bill"].append("IGST key is missing.")
                elif 'igst' in item:
                    if item['igst'] == '':
                        igst = 0.00
                    else:
                        igst = float(item['igst'])
                    self.passes["resource_and_bill"].append("IGST is present.")

                if 'total_inr' not in item:
                    self.errors["resource_and_bill"].append("Line item total INR key is missing.")
                elif 'total_inr' in item:
                    if item['total_inr'] == '':
                        total_inr = 0.00
                    else:
                        total_inr = float(item['total_inr'])
                    self.passes["resource_and_bill"].append("Total INR is present.")

            if 'total_inr' not in total_invoice_value:
                self.errors["resource_and_bill"].append("Invoice-level total INR key is missing.")
            elif 'total_inr' in total_invoice_value:
                if total_invoice_value['total_inr'] == '':
                    total_invoice_value_inr = 0.00
                else:
                    total_invoice_value_inr = float(total_invoice_value['total_inr'])
                self.passes["resource_and_bill"].append("Total invoice value in INR is present.")

            if 'in_words' not in total_invoice_value:
                self.errors["resource_and_bill"].append("Invoice total amount in words key is missing.")
            elif 'in_words' in total_invoice_value:
                if total_invoice_value['in_words'] == '':
                    total_invoice_value_words = ''
                else:
                    total_invoice_value_words = total_invoice_value['in_words']
                self.passes["resource_and_bill"].append("Total invoice value in words is present.")

            cgst_amt = round(((cgst_percent/100.0)*taxable_value), 2)
            sgst_amt = round(((sgst_percent/100.0)*taxable_value), 2)
            igst_amt = round(((igst_percent/100.0)*taxable_value), 2)

            if igst != 0.00:
                if cgst == 0.00 and sgst == 0.00:
                    if igst == igst_amt:
                        self.passes["resource_and_bill"].append(f"IGST is {igst} and correctly calculated at 18%. CGST and SGST are NIL.")
                    elif igst != igst_amt:
                        self.errors["resource_and_bill"].append(f"IGST is {igst} and incorrectly calculated. CGST and SGST are NIL.")
                elif cgst != 0.00 and sgst == 0.00:
                    self.errors["resource_and_bill"].append("IGST and CGST are both being charged.")
                elif cgst == 0.00 and sgst != 0.00:
                    self.errors["resource_and_bill"].append("IGST and SGST are both being charged.")
                elif cgst != 0.00 and sgst != 0.00:
                    self.errors["resource_and_bill"].append("IGST, CGST and SGST are all being charged.")
            elif igst == 0.00:
                if cgst != 0.00 and sgst != 0.00:
                    if cgst == cgst_amt and sgst == sgst_amt:
                        self.passes["resource_and_bill"].append(f"CGST is {cgst }and SGST is {sgst} and are correctly calculated at 9% each. IGST is NIL.")
                    elif cgst != cgst_amt and sgst == sgst_amt:
                        self.errors["resource_and_bill"].append(f"CGST is {cgst} and incorrectly calculated. CGST should be {cgst_amt}.")
                    elif cgst == cgst_amt and sgst != sgst_amt:
                        self.errors["resource_and_bill"].append(f"SGST is {sgst} and incorrectly calculated. SGST should be {sgst_amt}.")
                elif cgst == 0.00 and sgst != 0.00:
                    self.errors["resource_and_bill"].append("CGST is NIL. Should be calculated at 9% since IGST is NIL.")
                elif cgst != 0.00 and sgst == 0.00:
                    self.errors["resource_and_bill"].append("SGST is NIL. Should be calculated at 9% since IGST is NIL.")
                elif cgst == 0.00 and sgst == 0.00:
                    self.errors["resource_and_bill"].append("IGST, CGST and SGST are all NIL.")

            if total_inr != (taxable_value + cgst + sgst + igst):
                self.errors["resource_and_bill"].append("Computed line-item total does not match the sum of taxable value and taxes.")
            elif total_inr == (taxable_value + cgst + sgst + igst):
                self.passes["resource_and_bill"].append("Computed line-item total matches the sum of taxable value and taxes.")
            
            if total_inr != total_invoice_value_inr:
                self.errors["resource_and_bill"].append("Line-item total INR does not match invoice-level total INR.")
            elif total_inr == total_invoice_value_inr:
                self.passes["resource_and_bill"].append("Line-item total INR matches invoice-level total INR.")
            
            if total_invoice_value_words != number_to_words_inr(total_inr):
                self.errors["resource_and_bill"].append("Invoice total amount in words does not match the numeric total INR.")
            elif total_invoice_value_words == number_to_words_inr(total_inr):
                self.passes["resource_and_bill"].append("Invoice total amount in words matches the numeric total INR.")

    def validate_note(self, note: dict):
        """
        Validate the notes section of the invoice.
        
        Validates that notes 1 and 2 and the post-script match expected standard text.
        
        Args:
            note (dict): Dictionary containing note information with keys:
                - 1 (str): First note point
                - 2 (str): Second note point
                - post_script (str): Additional note or contact information
        """
        if '1' not in note:
            self.errors['note'].append("Note point 1 key is missing.")
        elif '1' in note:
            if is_value_present(note['1']) != True:
                self.errors['note'].append("Note point 1 value is missing or empty.")
            elif is_value_present(note['1']) == True:
                if note['1'] not in self.constants.NOTE_TEXT:
                    self.errors['note'].append("Note point 1 content does not match expected text.")
                elif note['1'] in self.constants.NOTE_TEXT:
                    self.passes['note'].append("Note point 1 is present and valid.")

        if '2' not in note:
            self.errors['note'].append("Note point 2 key is missing.")
        elif '2' in note:
            if is_value_present(note['2']) != True:
                self.errors['note'].append("Note point 2 value is missing or empty.")
            elif is_value_present(note['2']) == True:
                if note['2'] not in self.constants.NOTE_TEXT:
                    self.errors['note'].append("Note point 2 content does not match expected text.")
                elif note['2'] in self.constants.NOTE_TEXT:
                    self.passes['note'].append("Note point 2 is present and valid.")

        if 'post_script' not in note:
            self.errors['note'].append("Post script key is missing.")
        elif 'post_script' in note:
            if is_value_present(note['post_script']) != True:
                self.errors['note'].append("Post script value is missing or empty.")
            elif is_value_present(note['post_script']) == True:
                if note['post_script'] not in self.constants.NOTE_TEXT:
                    self.errors['note'].append("Post script content does not match expected text.")
                elif note['post_script'] in self.constants.NOTE_TEXT:
                    self.passes['note'].append("Post script is present and valid.")

    def validate_beneficiary_details(self, beneficiary: dict):
        """
        Validate beneficiary banking details.
        
        Validates presence of bank account information including beneficiary name,
        account number, IFSC code, and country.
        
        Args:
            beneficiary (dict): Dictionary containing beneficiary information with keys:
                - beneficiary_name (str): Name of the account holder
                - bank_name (str): Name of the bank
                - address (str): Bank branch address
                - account_no (str): Bank account number
                - ifsc_code (str): IFSC code of the bank branch
                - micr_code (str): MICR code
                - country (str): Country of the bank
                - reverse_charge (str): Reverse charge applicability
                - authorised_signatory (str): Name of authorized signatory
        """
        if 'beneficiary_name' not in beneficiary:
            self.errors["beneficiary"].append("Beneficiary name key is missing.")
        elif 'beneficiary_name' in beneficiary:
            if is_value_present(beneficiary['beneficiary_name']) != True:
                self.errors["beneficiary"].append("Beneficiary name value is missing or empty.")
            elif is_value_present(beneficiary['beneficiary_name']) == True:
                self.passes["beneficiary"].append("Beneficiary name is present.")

        if 'account_no' not in beneficiary:
            self.errors["beneficiary"].append("Account number key is missing.")
        elif 'account_no' in beneficiary:
            if is_value_present(beneficiary['account_no']) != True:
                self.errors["beneficiary"].append("Account number value is missing or empty.")
            elif is_value_present(beneficiary['account_no']) == True:
                self.passes["beneficiary"].append("Account number is present.")

        if 'ifsc_code' not in beneficiary:
            self.errors["beneficiary"].append("IFSC code key is missing.")
        elif 'ifsc_code' in beneficiary:
            if is_value_present(beneficiary['ifsc_code']) != True:
                self.errors["beneficiary"].append("IFSC code value is missing or empty.")
            elif is_value_present(beneficiary['ifsc_code']) == True:
                self.passes["beneficiary"].append("IFSC code is present.")

        if 'country' not in beneficiary:
            self.errors["beneficiary"].append("Country key is missing.")
        elif 'country' in beneficiary:
            if is_value_present(beneficiary['country']) != True:
                self.errors["beneficiary"].append("Country value is missing or empty.")
            elif is_value_present(beneficiary['country']) == True:
                self.passes["beneficiary"].append("Country is present.")

    def validate_qr_code(self, qr_code: str):
        """
        Validate QR code presence.
        
        Checks if QR code is marked as present in the invoice.
        
        Args:
            qr_code (str): String flag indicating QR code presence ("True" or "False").
        """
        if is_value_present(qr_code) != True:
            self.errors["qr_code"].append("QR code flag is missing.")
        elif is_value_present(qr_code) == True:
            if qr_code != "True":
                self.errors["qr_code"].append("QR code flag is present but marked as invalid.")
            elif qr_code == "True":
                self.passes["qr_code"].append("QR code is present and valid.")

    def validate_digital_signature(self, digital_signature: str):
        """
        Validate digital signature presence.
        
        Checks if digital signature is marked as present in the invoice.
        
        Args:
            digital_signature (str): String flag indicating digital signature presence 
                                    ("True" or "False").
        """
        if is_value_present(digital_signature) != True:
            self.errors["digital_signature"].append("Digital signature flag is missing.")
        elif is_value_present(digital_signature) == True:
            if digital_signature != "True":
                self.errors["digital_signature"].append("Digital signature flag is present but marked as invalid.")
            elif digital_signature == "True":
                self.passes["digital_signature"].append("Digital signature is present and valid.")
    
    def get_validation_results(self) -> Dict[str, Dict[str, List[str]]]:
        """
        Get comprehensive validation results.
        
        Returns:
            dict: Dictionary containing both errors and passes for all validated sections.
                  Structure: {"errors": {...}, "passes": {...}}
        """
        return {
            "errors": self.errors,
            "passes": self.passes
        }
    
    def has_errors(self) -> bool:
        """
        Check if any validation errors were found.
        
        Returns:
            bool: True if any section has errors, False otherwise.
        """
        return any(len(errors) > 0 for errors in self.errors.values())
    
    def get_error_count(self) -> int:
        """
        Get total count of validation errors across all sections.
        
        Returns:
            int: Total number of validation errors.
        """
        return sum(len(errors) for errors in self.errors.values())
    
    def get_pass_count(self) -> int:
        """
        Get total count of validation passes across all sections.
        
        Returns:
            int: Total number of validation passes.
        """
        return sum(len(passes) for passes in self.passes.values())


# Legacy function wrappers for backward compatibility

errors = {
    "letter_head": [],
    "tax_invoice": [],
    "bill_to": [],
    "invoice": [],
    "resource_and_bill": [],
    "note": [],
    "beneficiary": [],
    "qr_code": [],
    "digital_signature": []
}

passes = {
    "letter_head": [],
    "tax_invoice": [],
    "bill_to": [],
    "invoice": [],
    "resource_and_bill": [],
    "note": [],
    "beneficiary": [],
    "qr_code": [],
    "digital_signature": []
}

_validator = InvoiceValidator()


def validate_letter_head(letter_head: dict):
    """Legacy wrapper for backward compatibility."""
    global errors, passes, _validator
    _validator.validate_letter_head(letter_head)
    errors = _validator.errors
    passes = _validator.passes


def validate_tax_invoice(tax_invoice: dict):
    """Legacy wrapper for backward compatibility."""
    global errors, passes, _validator
    _validator.validate_tax_invoice(tax_invoice)
    errors = _validator.errors
    passes = _validator.passes


def validate_bill_to_details(bill_to: dict):
    """Legacy wrapper for backward compatibility."""
    global errors, passes, _validator
    _validator.validate_bill_to_details(bill_to)
    errors = _validator.errors
    passes = _validator.passes


def validate_invoice_details(invoice: dict):
    """Legacy wrapper for backward compatibility."""
    global errors, passes, _validator
    _validator.validate_invoice_details(invoice)
    errors = _validator.errors
    passes = _validator.passes


def validate_resource_and_bill_details(resource_and_bill: list, total_invoice_value: dict):
    """Legacy wrapper for backward compatibility."""
    global errors, passes, _validator
    _validator.validate_resource_and_bill_details(resource_and_bill, total_invoice_value)
    errors = _validator.errors
    passes = _validator.passes


def validate_note(note: dict):
    """Legacy wrapper for backward compatibility."""
    global errors, passes, _validator
    _validator.validate_note(note)
    errors = _validator.errors
    passes = _validator.passes


def validate_beneficiary_details(beneficiary: dict):
    """Legacy wrapper for backward compatibility."""
    global errors, passes, _validator
    _validator.validate_beneficiary_details(beneficiary)
    errors = _validator.errors
    passes = _validator.passes


def validate_qr_code(qr_code: str):
    """Legacy wrapper for backward compatibility."""
    global errors, passes, _validator
    _validator.validate_qr_code(qr_code)
    errors = _validator.errors
    passes = _validator.passes


def validate_digital_signature(digital_signature: str):
    """Legacy wrapper for backward compatibility."""
    global errors, passes, _validator
    _validator.validate_digital_signature(digital_signature)
    errors = _validator.errors
    passes = _validator.passes