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
         -F "file=@invoice.jpg"
"""

import os
import tempfile
import traceback
from typing import Dict, Any, Optional
from datetime import datetime

try:
    from fastapi import FastAPI, File, UploadFile, HTTPException, status
    from fastapi.responses import JSONResponse
    from fastapi.middleware.cors import CORSMiddleware
except ImportError:
    raise ImportError("Please install FastAPI: pip install fastapi uvicorn python-multipart")

from gemini_client import GeminiClient
from validator import InvoiceValidator


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
    
    def __init__(self):
        """Initialize the API with Gemini client and validator."""
        self.gemini_client = None
        self.validator = None
    
    def _initialize_clients(self):
        """Lazy initialization of clients to handle environment setup."""
        if self.gemini_client is None:
            self.gemini_client = GeminiClient()
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
        
        Args:
            upload_file (UploadFile): The uploaded file to validate.
        
        Raises:
            HTTPException: If validation fails.
        """
        # Check if file is provided
        if not upload_file:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No file provided"
            )
        
        # Check file size (e.g., max 10MB)
        max_size = 10 * 1024 * 1024  # 10MB in bytes
        upload_file.file.seek(0, 2)  # Seek to end
        file_size = upload_file.file.tell()
        upload_file.file.seek(0)  # Reset to beginning
        
        if file_size > max_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File size exceeds maximum allowed size of 10MB. Received: {file_size / (1024*1024):.2f}MB"
            )
        
        # Check file extension
        allowed_extensions = {'.jpg', '.jpeg', '.png', '.pdf', '.tiff', '.tif'}
        file_extension = os.path.splitext(upload_file.filename)[1].lower()
        
        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file type. Allowed types: {', '.join(allowed_extensions)}"
            )
    
    def _extract_data(self, image_path: str) -> Dict[str, Any]:
        """
        Extract data from invoice image.
        
        Args:
            image_path (str): Path to the invoice image.
        
        Returns:
            dict: Extracted invoice data.
        
        Raises:
            HTTPException: If extraction fails.
        """
        try:
            self._initialize_clients()
            extracted_data = self.gemini_client.extract_invoice_data(image_path)
            return extracted_data
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
        temp_file_path = None
        
        try:
            # Validate the uploaded file
            self._validate_file(upload_file)
            
            # Save to temporary location
            temp_file_path = self._save_uploaded_file(upload_file)
            
            # Extract data
            extracted_data = self._extract_data(temp_file_path)
            
            # Validate data
            validation_results = self._validate_data(extracted_data)
            
            # Build summary
            summary = self._build_summary(validation_results)
            
            # Build response
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
            # Re-raise HTTP exceptions as-is
            raise
        except Exception as e:
            # Catch any unexpected errors
            error_detail = {
                "error": str(e),
                "type": type(e).__name__,
                "traceback": traceback.format_exc()
            }
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unexpected error during processing: {str(e)}"
            )
        finally:
            # Clean up temporary file
            if temp_file_path:
                self._cleanup_temp_file(temp_file_path)


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
    try:
        # Check if required environment variables are set
        api_key_set = os.getenv("GEMINI_API_KEY") is not None
        model_name_set = os.getenv("MODEL_NAME") is not None
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "environment": {
                "gemini_api_key_configured": api_key_set,
                "model_name_configured": model_name_set
            },
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
        file (UploadFile): The invoice image file to process.
                          Supported formats: JPG, JPEG, PNG, PDF, TIFF
                          Max size: 10MB
    
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
            "filename": "invoice_001.jpg",
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
        file (UploadFile): The invoice image file to process.
    
    Returns:
        dict: JSON response with extracted data only.
    
    Example Response:
        {
            "status": "success",
            "timestamp": "2024-02-16T10:30:00.123456",
            "filename": "invoice_001.jpg",
            "extracted_data": {
                "letter_head": {...},
                "tax_invoice": {...},
                ...
            }
        }
    """
    temp_file_path = None
    
    try:
        # Validate the uploaded file
        api_handler._validate_file(file)
        
        # Save to temporary location
        temp_file_path = api_handler._save_uploaded_file(file)
        
        # Extract data
        extracted_data = api_handler._extract_data(temp_file_path)
        
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
    finally:
        if temp_file_path:
            api_handler._cleanup_temp_file(temp_file_path)


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