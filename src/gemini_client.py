#!/usr/bin/python3
"""
Gemini Client Module

This module provides a client interface for the Google Gemini API to extract
structured data from invoice images using AI-powered OCR and data extraction.
"""
from dotenv import load_dotenv
load_dotenv()

import os

try:
    from google import genai
    from google.genai import types
except ImportError:
    raise ImportError("Please run `pip install google-genai` package to use the Gemini client.")


class GeminiClient:
    """
    A client for interacting with Google's Gemini API to extract structured invoice data.
    
    Attributes:
        api_key (str): The API key for authenticating with Gemini API.
        model_name (str): The name of the Gemini model to use for generation.
        client (genai.Client): The initialized Gemini API client.
    """
    
    def __init__(self, api_key: str = os.getenv("GEMINI_API_KEY"),
                 model_name: str = os.getenv("MODEL_NAME")):
        """
        Initialize the Gemini client with API credentials and model configuration.
        
        Args:
            api_key (str): The API key for Gemini API authentication.
            model_name (str): The Gemini model name to use for content generation.
        
        Raises:
            ImportError: If the API key is not configured properly.
        """
        self.api_key = api_key
        self.model_name = model_name
        
        try:
            self.client = genai.Client(api_key=self.api_key)
        except Exception:
            if self.api_key is not None:
                raise ImportError("API key not configured properly.")
            else:
                raise ImportError("API key not provided.")
    
    def _get_response_schema(self) -> dict:
        """
        Define the JSON schema for structured invoice data extraction.
        
        Returns:
            dict: A comprehensive JSON schema defining the structure of invoice data
                  including letter head, tax details, billing information, and more.
        """
        response_schema = {
            "type": "object",
            "properties": {
                "letter_head": {
                    "type": "object",
                    "properties": {
                        "company_name": {"type": "string"},
                        "former_company_name": {"type": "string"},
                        "address": {"type": "string"},
                        "cin": {"type": "string"},
                        "gstin": {"type": "string"},
                        "phone": {"type": "string"},
                        "email": {"type": "string"},
                        "website": {"type": "string"}
                    },
                    "required": [
                        "company_name",
                        "former_company_name",
                        "address",
                        "cin",
                        "gstin",
                        "phone",
                        "email",
                        "website"
                    ]
                },

                "tax_invoice": {
                    "type": "object",
                    "properties": {
                        "pan_no": {"type": "string"},
                        "tan_no": {"type": "string"}
                    },
                    "required": ["pan_no", "tan_no"]
                },

                "bill_to_details": {
                    "type": "object",
                    "properties": {
                        "company_name": {"type": "string"},
                        "address": {"type": "string"},
                        "gstin": {"type": "string"},
                        "pan_no": {"type": "string"},
                        "tan_no": {"type": "string"},
                        "place_of_supply": {"type": "string"},
                        "irn_no": {"type": "string"}
                    },
                    "required": [
                        "company_name",
                        "address",
                        "gstin",
                        "pan_no",
                        "tan_no",
                        "place_of_supply",
                        "irn_no"
                    ]
                },

                "invoice_details": {
                    "type": "object",
                    "properties": {
                        "date": {"type": "string"},
                        "invoice_no": {"type": "string"},
                        "service_month": {"type": "string"},
                        "lower_tds_cert_no": {"type": "string"}
                    },
                    "required": [
                        "date",
                        "invoice_no",
                        "service_month",
                        "lower_tds_cert_no"
                    ]
                },

                "resource_and_bill_details": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "properties": {
                            "sl_no": {"type": "string"},
                            "resource_name": {"type": "string"},
                            "hsn_sac": {"type": "string"},
                            "po_no": {"type": "string"},
                            "bill_rate": {"type": "string"},
                            "ericsson_invoice_code": {"type": "string"},
                            "taxable_value": {"type": "string"},
                            "cgst": {"type": "string"},
                            "sgst": {"type": "string"},
                            "igst": {"type": "string"},
                            "total_inr": {"type": "string"}
                        },
                        "required": [
                            "sl_no",
                            "resource_name",
                            "hsn_sac",
                            "po_no",
                            "bill_rate",
                            "ericsson_invoice_code",
                            "taxable_value",
                            "cgst",
                            "sgst",
                            "igst",
                            "total_inr"
                        ]
                    }
                },

                "total_invoice_value": {
                    "type": "object",
                    "properties": {
                        "taxable_value": {"type": "string"},
                        "cgst": {"type": "string"},
                        "sgst": {"type": "string"},
                        "igst": {"type": "string"},
                        "total_inr": {"type": "string"},
                        "in_words": {"type": "string"}
                    },
                    "required": [
                        "taxable_value",
                        "cgst",
                        "sgst",
                        "igst",
                        "total_inr",
                        "in_words"
                    ]
                },

                "arn_for_lut": {"type": "string"},

                "supply": {"type": "string"},

                "igst_foregone": {"type": "string"},

                "note": {
                    "type": "object",
                    "properties": {
                        "1": {"type": "string"},
                        "2": {"type": "string"},
                        "post_script": {"type": "string"}
                    },
                    "required": [
                        "1",
                        "2",
                        "post_script"
                    ]
                },

                "beneficiary_details": {
                    "type": "object",
                    "properties": {
                        "beneficiary_name": {"type": "string"},
                        "bank_name": {"type": "string"},
                        "address": {"type": "string"},
                        "reverse_charge": {"type": "string"},
                        "account_no": {"type": "string"},
                        "ifsc_code": {"type": "string"},
                        "micr_code": {"type": "string"},
                        "country": {"type": "string"},
                        "authorised_signatory": {"type": "string"}
                    },
                    "required": [
                        "beneficiary_name",
                        "bank_name",
                        "address",
                        "reverse_charge",
                        "account_no",
                        "ifsc_code",
                        "micr_code",
                        "country",
                        "authorised_signatory"
                    ]
                },

                "qr_code": {"type": "string"},

                "digital_signature": {"type": "string"}
            },
            "required": [
                "letter_head",
                "tax_invoice",
                "bill_to_details",
                "invoice_details",
                "resource_and_bill_details",
                "total_invoice_value",
                "arn_for_lut",
                "supply",
                "igst_foregone",
                "note",
                "beneficiary_details",
                "qr_code",
                "digital_signature"
            ]
        }
        
        return response_schema
    
    def _get_extraction_prompt(self) -> str:
        """
        Generate the detailed prompt for invoice data extraction.
        
        Returns:
            str: A comprehensive prompt with extraction rules and examples.
        """
        prompt = """Extract data from the provided invoice image.

Rules:

Return ONLY the actual address (uptill the PIN code).

Return ONLY the actual values, NOT the labels.
Example 1: From "CIN No:U74140WB1993PLC059586", return only "U74140WB1993PLC059586"
Example 2: From "Pan No : AACCE4175D", return only "AACCE4175D"
Example 3: From "TAN NO : CALG02952F", return only "CALG02952F"

Preserve formatting.
Example 1: From "(Formerly known as Genius Consultants Limited)", return "(Formerly known as Genius Consultants Limited)" and not "Formerly known as Genius Consultants Limited"
Example 2: From "GWBIAR/NV0001/26", return "GWBIAR/NV0001/26" and not "GWBIARNV000126" or "GWBIAR NV000 126" or something else
Example 3: From "AACCE4175D", return "AACCE4175D" and not "AACC E4175D" or something else

For blank fields, STRICTLY return "".

For Resource and Bill Details and Total Invoice Value, properly follow table outlines to extract the data.

For the Note, maintain a clear separation of points 1 and 2, and, the post script.

For the QR Code, return "True" (if Present) or "False" (if Absent).

For Digital Signature, return "True" (if Present) or "False" (if Absent).

If there are any key objects that are missing, do NOT omit them. Instead return "" as values against the keys."""
        
        return prompt
    
    def call_llm(self, prompt: str, image_path: str, response_schema: dict):
        """
        Make an API call to the Gemini model with the provided image and prompt.
        
        Args:
            prompt (str): The extraction prompt with instructions for the model.
            image_path (str): Path to the invoice image file.
            response_schema (dict): JSON schema defining the expected response structure.
        
        Returns:
            genai.types.GenerateContentResponse: The raw response from the Gemini API.
        
        Raises:
            ImportError: If the image path is invalid or not provided.
        """
        try:
            with open(image_path, 'rb') as f:
                image_bytes = f.read()
        except Exception:
            if image_path is not None:
                raise ImportError("Image path provided is invalid.")
            else:
                raise ImportError("Image path not provided.")

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=[
                types.Part.from_bytes(
                    data=image_bytes,
                    mime_type='image/jpeg',
                ),
                prompt
            ],
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_budget=0),  # Disables thinking
                system_instruction="""You are an expert at extracting structured data from images.
Return ONLY a valid JSON object that strictly adheres to the specified schema.
If a value is missing, return an empty string "".""",
                temperature=0.1,
                response_mime_type="application/json",
                response_schema=response_schema
            )
        )

        return response

    def extract_invoice_data(self, image_path: str) -> dict:
        """
        Extract structured data from an invoice image using the Gemini API.
        
        This is the main public method that orchestrates the entire extraction process.
        It loads the image, applies the extraction prompt, and returns parsed JSON data.
        
        Args:
            image_path (str): Path to the invoice image file to process.
        
        Returns:
            dict: Parsed JSON response containing all extracted invoice data fields.
        """
        response_schema = self._get_response_schema()
        prompt = self._get_extraction_prompt()
        
        response = self.call_llm(prompt, image_path, response_schema)
        
        return response.parsed


def gemini_client(image_path: str):
    """
    Legacy function wrapper for backward compatibility.
    
    Calls the Gemini API to extract structured data from invoice image.
    
    Args:
        image_path (str): Path to the image file.
    
    Returns:
        dict: RAW JSON response from Gemini API.
    """
    client = GeminiClient()
    return client.extract_invoice_data(image_path)