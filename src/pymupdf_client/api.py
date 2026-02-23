#!/usr/bin/python3
"""
Invoice Processing API

This module provides a RESTful API for invoice processing. It accepts invoice images,
extracts structured data using AI, validates the extracted information, and returns
comprehensive JSON responses including extraction results and validation reports.

The API is built using FastAPI and supports:
- Single invoice image upload and processing
- Health check endpoint
- Detailed error handling
- CORS support for web applications

Dependencies:
    - fastapi
    - uvicorn
    - python-multipart (for file uploads)
    
Usage:
    uvicorn api:app --host 0.0.0.0 --port 8000 --reload
    
Example API Calls:
    # Health check
    curl http://localhost:8000/health
    
    # Process invoice
    curl -X POST http://localhost:8000/process-invoice \
         -F "file=@invoice.pdf"
"""

import os
import tempfile
import traceback
from typing import Dict, Any, Optional
from datetime import datetime
from datetime import timezone

try:
    from fastapi import FastAPI, File, UploadFile, HTTPException, status
    from fastapi.responses import JSONResponse
    from fastapi.middleware.cors import CORSMiddleware
except ImportError:
    raise ImportError("Please install FastAPI: pip install fastapi uvicorn python-multipart")

# from gemini_client import GeminiClient
from pdf_client import PyMuPDFClient
from validator import InvoiceValidator
from helper import pdf_to_png_images, are_pdf_pages_blank
from helper import fetch_digital_invoices, download_pdf_from_url, load_processed_log, update_processed_log

# Initialize FastAPI app
app = FastAPI(
    title="Invoice Processing API",
    description="AI-powered invoice data extraction and validation API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS - adjust origins as needed for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class InvoiceProcessingAPI:
    """
    Core API logic for invoice processing.
    
    This class encapsulates the business logic for processing invoices,
    separating it from the FastAPI route handlers.
    """
    
    # def __init__(self):
    #     """Initialize the API with Gemini client and validator."""
    #     self.gemini_client = None
    #     self.validator = None

    def __init__(self):
        """Initialize the API with PyMuPDF client and validator."""
        self.pdf_client = None
        self.validator = None
    
    # def _initialize_clients(self):
    #     """Lazy initialization of clients to handle environment setup."""
    #     if self.gemini_client is None:
    #         self.gemini_client = GeminiClient()
    #     if self.validator is None:
    #         self.validator = InvoiceValidator()

    def _initialize_clients(self):
        """Lazy initialization of clients to handle environment setup."""
        if self.validator is None:
            self.validator = InvoiceValidator()
    
    def _save_uploaded_file(self, upload_file: UploadFile) -> str:
        """
        Save uploaded file to a temporary location.
        
        Args:
            upload_file (UploadFile): The uploaded file from FastAPI.
        
        Returns:
            str: Path to the saved temporary file.
        
        Raises:
            HTTPException: If file saving fails.
        """
        try:
            # Create a temporary file with the same extension
            suffix = os.path.splitext(upload_file.filename)[1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                # Read and write the uploaded file content
                content = upload_file.file.read()
                tmp_file.write(content)
                tmp_file.flush()
                return tmp_file.name
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save uploaded file: {str(e)}"
            )
    
    def _cleanup_temp_file(self, file_path: str):
        """
        Clean up temporary file.
        
        Args:
            file_path (str): Path to the temporary file to delete.
        """
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            # Log error but don't fail the request
            print(f"Warning: Failed to cleanup temporary file {file_path}: {e}")
    
    def _validate_file(self, upload_file: UploadFile):
        """
        Validate the uploaded file.

        Only PDF files are accepted. The file must also be within the
        10 MB size limit.  Structural PDF checks (page count, blank page)
        are performed separately in _validate_pdf_structure after the
        file has been saved to disk.

        Args:
            upload_file (UploadFile): The uploaded file to validate.

        Raises:
            HTTPException 400: If no file is provided.
            HTTPException 400: If the file exceeds 10 MB.
            HTTPException 400: If the file is not a PDF.
        """
        # Check if file is provided
        if not upload_file:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No file provided"
            )

        # Check file size (max 10 MB)
        max_size = 10 * 1024 * 1024  # 10 MB in bytes
        upload_file.file.seek(0, 2)  # Seek to end
        file_size = upload_file.file.tell()
        upload_file.file.seek(0)  # Reset to beginning

        if file_size > max_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"File size exceeds the maximum allowed size of 10 MB. "
                    f"Received: {file_size / (1024 * 1024):.2f} MB"
                )
            )

        # Only PDF files are accepted
        file_extension = os.path.splitext(upload_file.filename)[1].lower()
        if file_extension != ".pdf":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Invalid file type '{file_extension}'. "
                    "Only PDF files (.pdf) are accepted."
                )
            )

    def _validate_pdf_structure(self, pdf_path: str):
        """
        Validate the structural integrity of the uploaded PDF.

        Rules:
            1. The PDF must be exactly **1 page** long.
            2. The first (and only) page must **not** be blank.

        Args:
            pdf_path (str): Absolute path to the temporary PDF file on disk.

        Raises:
            HTTPException 400: If the PDF contains more than one page.
            HTTPException 400: If the first page is detected as blank.
        """
        # Render all pages to PIL images (low DPI is fast enough for counting)
        pages = pdf_to_png_images(pdf_path, dpi=150)

        # Rule 1 — must be exactly one page
        if len(pages) > 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Invalid PDF: the file contains {len(pages)} pages. "
                    "Only single-page invoices are accepted."
                )
            )

        # Rule 2 — the page must not be blank
        blank_flags = are_pdf_pages_blank(pdf_path, dpi=150)
        if blank_flags[0]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid PDF: the first page is blank."
            )

    # def _convert_pdf_to_jpg_tmpfile(self, pdf_path: str) -> str:
    #     """
    #     Render the first page of the validated PDF to a JPEG temporary file.

    #     The JPEG temp file is what gets passed to the Gemini client for
    #     data extraction. The caller is responsible for deleting it after
    #     use via _cleanup_temp_file.

    #     Args:
    #         pdf_path (str): Absolute path to the validated PDF file.

    #     Returns:
    #         str: Absolute path to the created JPEG temporary file.

    #     Raises:
    #         HTTPException 500: If rendering or saving the JPEG fails.
    #     """
    #     try:
    #         pages = pdf_to_png_images(pdf_path, dpi=200)
    #         page_image = pages[0].convert("RGB")  # JPEG requires RGB mode

    #         tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    #         tmp.close()  # Close so PIL can open and write on all platforms
    #         page_image.save(tmp.name, format="JPEG", quality=95)
    #         return tmp.name
    #     except Exception as e:
    #         raise HTTPException(
    #             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    #             detail=f"Failed to convert PDF page to JPEG: {str(e)}"
    #         )
    
    # def _extract_data(self, image_path: str) -> Dict[str, Any]:
    #     """
    #     Extract data from invoice image.
        
    #     Args:
    #         image_path (str): Path to the invoice image.
        
    #     Returns:
    #         dict: Extracted invoice data.
        
    #     Raises:
    #         HTTPException: If extraction fails.
    #     """
    #     try:
    #         self._initialize_clients()
    #         extracted_data = self.gemini_client.extract_invoice_data(image_path)
    #         return extracted_data
    #     except Exception as e:
    #         raise HTTPException(
    #             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    #             detail=f"Data extraction failed: {str(e)}"
    #         )

    def _extract_data(self, pdf_path: str) -> Dict[str, Any]:
        """
        Extract data from invoice PDF.
        
        Args:
            pdf_path (str): Path to the invoice PDF.
        ...
        """
        try:
            client = PyMuPDFClient(pdf_path)
            return client.extract_invoice_data()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Data extraction failed: {str(e)}"
            )
    
    def _validate_data(self, extracted_data: Dict[str, Any]) -> Dict[str, Dict]:
        """
        Validate extracted invoice data.
        
        Args:
            extracted_data (dict): Extracted invoice data.
        
        Returns:
            dict: Validation results with errors and passes.
        """
        self._initialize_clients()
        
        # Create a new validator instance for this request
        validator = InvoiceValidator()
        
        # Validate each section
        if 'letter_head' in extracted_data:
            validator.validate_letter_head(extracted_data['letter_head'])
        
        if 'tax_invoice' in extracted_data:
            validator.validate_tax_invoice(extracted_data['tax_invoice'])
        
        if 'bill_to_details' in extracted_data:
            validator.validate_bill_to_details(extracted_data['bill_to_details'])
        
        if 'invoice_details' in extracted_data:
            validator.validate_invoice_details(extracted_data['invoice_details'])
        
        if 'resource_and_bill_details' in extracted_data and 'total_invoice_value' in extracted_data:
            validator.validate_resource_and_bill_details(
                extracted_data['resource_and_bill_details'],
                extracted_data['total_invoice_value']
            )
        
        if 'note' in extracted_data:
            validator.validate_note(extracted_data['note'])
        
        if 'beneficiary_details' in extracted_data:
            validator.validate_beneficiary_details(extracted_data['beneficiary_details'])
        
        if 'qr_code' in extracted_data:
            validator.validate_qr_code(extracted_data['qr_code'])
        
        if 'digital_signature' in extracted_data:
            validator.validate_digital_signature(extracted_data['digital_signature'])
        
        return validator.get_validation_results()
    
    def _build_summary(self, validation_results: Dict[str, Dict]) -> Dict[str, Any]:
        """
        Build validation summary statistics.
        
        Args:
            validation_results (dict): Validation results with errors and passes.
        
        Returns:
            dict: Summary statistics including counts and success rate.
        """
        error_count = sum(len(errors) for errors in validation_results['errors'].values())
        pass_count = sum(len(passes) for passes in validation_results['passes'].values())
        total_checks = error_count + pass_count
        
        summary = {
            "total_checks": total_checks,
            "passed": pass_count,
            "failed": error_count,
            "success_rate": round((pass_count / total_checks * 100), 2) if total_checks > 0 else 0.0,
            "status": "success" if error_count == 0 else "validation_errors"
        }
        
        return summary
    
    def process_invoice(self, upload_file: UploadFile) -> Dict[str, Any]:
        """
        Complete invoice processing workflow.
        
        Args:
            upload_file (UploadFile): Uploaded invoice image file.
        
        Returns:
            dict: Complete response with extracted data, validation results, and summary.
        
        Raises:
            HTTPException: If any step of processing fails.
        """
        pdf_tmp_path = None
        # jpg_tmp_path = None

        try:
            # Step 1 — basic file validation (type + size)
            self._validate_file(upload_file)

            # Step 2 — persist the PDF to a temp file so we can inspect it
            pdf_tmp_path = self._save_uploaded_file(upload_file)

            # Step 3 — structural PDF validation (page count + blank check)
            self._validate_pdf_structure(pdf_tmp_path)

            # # Step 4 — render the PDF page to a JPEG temp file
            # jpg_tmp_path = self._convert_pdf_to_jpg_tmpfile(pdf_tmp_path)

            # # Step 5 — extract structured data from the JPEG via Gemini
            # extracted_data = self._extract_data(jpg_tmp_path)

            # Step 4 — extract structured data directly from the PDF
            extracted_data = self._extract_data(pdf_tmp_path)

            # Step 6 — validate extracted data
            validation_results = self._validate_data(extracted_data)

            # Step 7 — build summary + response
            summary = self._build_summary(validation_results)

            response = {
                "status": "success",
                "timestamp": datetime.utcnow().isoformat(),
                "filename": upload_file.filename,
                "summary": summary,
                "extracted_data": extracted_data,
                "validation_results": validation_results
            }

            return response

        except HTTPException:
            # Re-raise HTTP exceptions (400 / 500) as-is
            raise
        except Exception as e:
            # Catch any unexpected errors
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unexpected error during processing: {str(e)}"
            )
        # finally:
        #     # Always clean up both temp files, even if an exception occurred
        #     for path in (pdf_tmp_path, jpg_tmp_path):
        #         if path:
        #             self._cleanup_temp_file(path)

        finally:
            if pdf_tmp_path:
                self._cleanup_temp_file(pdf_tmp_path)


# Create API instance
api_handler = InvoiceProcessingAPI()


# ============================================================================
# API Route Handlers
# ============================================================================

@app.get("/", tags=["General"])
async def root():
    """
    Root endpoint providing API information.
    
    Returns:
        dict: Basic API information and available endpoints.
    """
    return {
        "name": "Invoice Processing API",
        "version": "1.0.0",
        "description": "AI-powered invoice data extraction and validation",
        "endpoints": {
            "health": "/health",
            "process_invoice": "/process-invoice (POST)",
            "docs": "/docs",
            "redoc": "/redoc"
        },
        "status": "operational"
    }


@app.get("/health", tags=["General"])
async def health_check():
    """
    Health check endpoint.
    
    Returns:
        dict: API health status and system information.
    """
    # try:
    #     # Check if required environment variables are set
    #     api_key_set = os.getenv("GEMINI_API_KEY") is not None
    #     model_name_set = os.getenv("MODEL_NAME") is not None
        
    #     return {
    #         "status": "healthy",
    #         "timestamp": datetime.utcnow().isoformat(),
    #         "environment": {
    #             "gemini_api_key_configured": api_key_set,
    #             "model_name_configured": model_name_set
    #         },
    #         "dependencies": {
    #             "gemini_client": "available",
    #             "validator": "available"
    #         }
    #     }
    # except Exception as e:
    #     return JSONResponse(
    #         status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    #         content={
    #             "status": "unhealthy",
    #             "error": str(e),
    #             "timestamp": datetime.utcnow().isoformat()
    #         }
    #     )
    
    try:
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "dependencies": {
                "gemini_client": "available",
                "validator": "available"
            }
        }
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )


@app.post("/process-invoice", tags=["Invoice Processing"])
async def process_invoice_endpoint(file: UploadFile = File(...)):
    """
    Process an invoice image and return extracted data with validation results.
    
    This endpoint accepts an invoice image file, extracts structured data using AI,
    validates the extracted information, and returns a comprehensive JSON response.
    
    Args:
        file (UploadFile): The invoice PDF file to process.
                          Supported format: PDF (.pdf)
                          Max size: 10 MB
    
    Returns:
        dict: JSON response containing:
            - status: Overall processing status
            - timestamp: Processing timestamp (UTC)
            - filename: Original uploaded filename
            - summary: Validation summary with statistics
            - extracted_data: Complete extracted invoice data
            - validation_results: Detailed validation errors and passes
    
    Raises:
        HTTPException 400: If file validation fails
        HTTPException 500: If processing fails
    
    Example Response:
        {
            "status": "success",
            "timestamp": "2024-02-16T10:30:00.123456",
            "filename": "invoice_001.pdf",
            "summary": {
                "total_checks": 50,
                "passed": 48,
                "failed": 2,
                "success_rate": 96.0,
                "status": "validation_errors"
            },
            "extracted_data": {
                "letter_head": {...},
                "tax_invoice": {...},
                ...
            },
            "validation_results": {
                "errors": {...},
                "passes": {...}
            }
        }
    """
    try:
        result = api_handler.process_invoice(file)
        return JSONResponse(content=result, status_code=status.HTTP_200_OK)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@app.post("/extract-only", tags=["Invoice Processing"])
async def extract_only_endpoint(file: UploadFile = File(...)):
    """
    Extract data from invoice without validation.
    
    This endpoint only performs data extraction without validation,
    useful when you need raw extracted data quickly.
    
    Args:
        file (UploadFile): The invoice PDF file to process.
    
    Returns:
        dict: JSON response with extracted data only.
    
    Example Response:
        {
            "status": "success",
            "timestamp": "2024-02-16T10:30:00.123456",
            "filename": "invoice_001.pdf",
            "extracted_data": {
                "letter_head": {...},
                "tax_invoice": {...},
                ...
            }
        }
    """
    pdf_tmp_path = None
    # jpg_tmp_path = None

    try:
        # Step 1 — basic file validation (type + size)
        api_handler._validate_file(file)

        # Step 2 — persist the PDF to a temp file
        pdf_tmp_path = api_handler._save_uploaded_file(file)

        # Step 3 — structural PDF validation (page count + blank check)
        api_handler._validate_pdf_structure(pdf_tmp_path)

        # # Step 4 — render the PDF page to a JPEG temp file
        # jpg_tmp_path = api_handler._convert_pdf_to_jpg_tmpfile(pdf_tmp_path)

        # # Step 5 — extract structured data from the JPEG via Gemini
        # extracted_data = api_handler._extract_data(jpg_tmp_path)

        # Step 4 — extract structured data directly from the PDF
        extracted_data = api_handler._extract_data(pdf_tmp_path)

        # Build response
        response = {
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
            "filename": file.filename,
            "extracted_data": extracted_data
        }

        return JSONResponse(content=response, status_code=status.HTTP_200_OK)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Extraction failed: {str(e)}"
        )
    # finally:
    #     # Always clean up both temp files
    #     for path in (pdf_tmp_path, jpg_tmp_path):
    #         if path:
    #             api_handler._cleanup_temp_file(path)

    finally:
            if pdf_tmp_path:
                api_handler._cleanup_temp_file(pdf_tmp_path)


@app.post("/process-invoices-from-api", tags=["Invoice Processing"])
async def process_invoices_from_api_endpoint():
    """
    Fetch invoices from the client's GSPPI API and process all of them.

    Every invoice returned by the GSPPI API is processed unconditionally.
    The client controls the API response — successfully processed invoices
    are removed by the client, and failed ones are fixed and resent.

    Each invoice's outcome is written to the processed log immediately after
    processing. If a BillID already exists in the log (previously failed and
    resent by the client), its entry is overwritten with the latest outcome.

    Returns:
        dict: JSON response containing:
            - status (str): 'success' (even if some invoices failed individually)
            - timestamp (str): UTC timestamp of the run
            - summary (dict): Counts of total fetched, succeeded, failed
            - results (dict): Per-BillID outcome keyed by BillID, each containing:
                - bill_id (str)
                - doc_type (str)
                - url (str)
                - status (str): 'success' or 'failed'
                - error (str, optional): present only when status is 'failed'
                - extracted_data (dict, optional): present only on success
                - validation_results (dict, optional): present only on success
                - validation_summary (dict, optional): present only on success

    Raises:
        HTTPException 500: If the GSPPI API itself cannot be reached.
    """
    # Step 1 — fetch the full invoice list from the client API
    try:
        invoice_list = fetch_digital_invoices()
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch invoices from GSPPI API: {str(e)}"
        )

    results = {}
    succeeded = 0
    failed = 0

    for invoice in invoice_list:
        bill_id = invoice.get("BillID", "")
        url = invoice.get("Url", "")
        doc_type = invoice.get("DocType", "")

        pdf_tmp_path = None
        # jpg_tmp_path = None

        try:
            # Step 2 — download the PDF to a temp file
            pdf_tmp_path = download_pdf_from_url(url)

            # Step 3 — structural PDF validation (page count + blank check)
            api_handler._validate_pdf_structure(pdf_tmp_path)

            # # Step 4 — render to JPEG for Gemini
            # jpg_tmp_path = api_handler._convert_pdf_to_jpg_tmpfile(pdf_tmp_path)

            # # Step 5 — extract structured data via Gemini
            # extracted_data = api_handler._extract_data(jpg_tmp_path)

            # Step 4 — extract structured data directly from the PDF
            extracted_data = api_handler._extract_data(pdf_tmp_path)

            # Step 6 — validate extracted data
            validation_results = api_handler._validate_data(extracted_data)

            # Step 7 — build summary
            validation_summary = api_handler._build_summary(validation_results)

            # Step 8 — write success to log
            update_processed_log(bill_id, status="success", url=url, doc_type=doc_type)

            succeeded += 1
            results[bill_id] = {
                "bill_id": bill_id,
                "doc_type": doc_type,
                "url": url,
                "status": "success",
                "extracted_data": extracted_data,
                "validation_results": validation_results,
                "validation_summary": validation_summary
            }

        except Exception as e:
            error_message = str(e)

            # Write failure to log, overwriting any previous entry for this BillID
            update_processed_log(bill_id, status="failed", url=url, doc_type=doc_type, error=error_message)

            failed += 1
            results[bill_id] = {
                "bill_id": bill_id,
                "doc_type": doc_type,
                "url": url,
                "status": "failed",
                "error": error_message
            }

        # finally:
        #     # Always clean up temp files for this invoice
        #     for path in (pdf_tmp_path, jpg_tmp_path):
        #         if path:
        #             api_handler._cleanup_temp_file(path)

        finally:
            if pdf_tmp_path:
                api_handler._cleanup_temp_file(pdf_tmp_path)

    return JSONResponse(
        content={
            "status": "success",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_fetched": len(invoice_list),
                "succeeded": succeeded,
                "failed": failed
            },
            "results": results
        },
        status_code=status.HTTP_200_OK
    )


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """
    Global exception handler for unexpected errors.
    
    Args:
        request: The request that caused the exception.
        exc: The exception that was raised.
    
    Returns:
        JSONResponse: Error response with details.
    """
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "error",
            "message": "An unexpected error occurred",
            "detail": str(exc),
            "timestamp": datetime.utcnow().isoformat()
        }
    )


# ============================================================================
# Main entry point for running with uvicorn
# ============================================================================

if __name__ == "__main__":
    try:
        import uvicorn
    except ImportError:
        print("Error: uvicorn is not installed.")
        print("Please install it using: pip install uvicorn")
        exit(1)
    
    print("Starting Invoice Processing API...")
    print("API Documentation: http://localhost:8000/docs")
    print("Alternative Docs: http://localhost:8000/redoc")
    
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )