"""
Helper Module

This module provides utility functions for invoice data processing,
including number-to-words conversion and value validation.
"""

try:
    from num2words import num2words
except ImportError:
    raise ImportError("Please install num2words: pip install num2words")

try:
    from pdf2image import convert_from_path
except ImportError:
    raise ImportError("Please install pdf2image: pip install pdf2image")

import numpy as np
from PIL import Image
from pathlib import Path

import json
import os
import requests
from datetime import datetime, timezone

def number_to_words_inr(amount: float) -> str:
    """
    Convert a numeric amount to its word representation in Indian Rupees format.
    
    This function converts a decimal amount into a properly formatted string
    representation following Indian English conventions for currency.
    
    Args:
        amount (float): The monetary amount to convert (e.g., 12345.67).
    
    Returns:
        str: The amount in words formatted as "Rupees [Amount] and [Paisa] Paisa Only."
             Example: "Rupees Twelve Thousand Three Hundred Forty Five and Sixty Seven Paisa Only."
             If there are no paise, returns: "Rupees [Amount] and Paisa Only."
    
    Examples:
        >>> number_to_words_inr(1234.56)
        'Rupees One Thousand Two Hundred Thirty Four and Fifty Six Paisa Only.'
        
        >>> number_to_words_inr(5000.00)
        'Rupees Five Thousand and Paisa Only.'
    """
    rupees = int(amount)
    paise = int(round((amount - rupees) * 100))

    rupees_words = num2words(rupees, lang="en_IN").replace("-", " ").title()

    rupees_words = (
        rupees_words
        .replace("-", "")
        .replace(",", "")
        .replace(" and ", " ")
        .replace(" And ", " ")
        .title()
    )

    if paise > 0:
        paise_words = num2words(paise, lang="en_IN").replace("-", " ").title()
        return f"Rupees {rupees_words} and {paise_words} Paisa Only."
    else:
        return f"Rupees {rupees_words} and Paisa Only."
    

def is_value_present(value) -> bool:
    """
    Check if a value is present and non-empty.
    
    This function validates whether a value contains actual data or is effectively empty.
    It handles various data types including None, strings, lists, and dictionaries.
    
    Args:
        value: The value to check. Can be of any type (str, list, dict, None, etc.).
    
    Returns:
        bool: True if the value is present and non-empty, False otherwise.
        
    Examples:
        >>> is_value_present(None)
        False
        
        >>> is_value_present("")
        False
        
        >>> is_value_present("   ")
        False
        
        >>> is_value_present("Hello")
        True
        
        >>> is_value_present([])
        False
        
        >>> is_value_present([1, 2, 3])
        True
        
        >>> is_value_present({})
        False
        
        >>> is_value_present({"key": "value"})
        True
    """
    if value is None:
        return False
    if isinstance(value, str) and value.strip() == "":
        return False
    if isinstance(value, (list, dict)) and len(value) == 0:
        return False
    return True


def pdf_to_png_images(
    pdf_path: str,
    dpi: int = 200,
    output_dir: str | None = None,
) -> list:
    """
    Convert every page of a PDF file into a PNG image.

    Args:
        pdf_path (str): Path to the source PDF file.
        dpi (int): Rendering resolution in dots-per-inch (default: 200).
            Higher values produce sharper images but larger files.
        output_dir (str | None): Optional directory to save the PNG files.
            If provided, each page is saved as ``page_<n>.png`` (1-indexed)
            inside that directory. The directory is created automatically
            when it does not exist. When ``None`` (default) no files are
            written to disk.

    Returns:
        list[PIL.Image.Image]: A list of PIL Image objects, one per page,
        in document order.

    Raises:
        FileNotFoundError: If *pdf_path* does not point to an existing file.
        ImportError: If ``pdf2image`` is not installed or Poppler is missing.

    Examples:
        >>> images = pdf_to_png_images("document.pdf")
        >>> print(len(images), "pages converted")

        >>> # Save to disk and keep the PIL objects
        >>> images = pdf_to_png_images("document.pdf", dpi=300, output_dir="out/")
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    images = convert_from_path(str(pdf_path), dpi=dpi, fmt="png")

    if output_dir is not None:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        for idx, img in enumerate(images, start=1):
            img.save(out / f"page_{idx}.png", format="PNG")

    return images


def are_pdf_pages_blank(
    pdf_path: str,
    dpi: int = 200,
    brightness_threshold: float = 253.0,
    white_pixel_ratio: float = 0.999,
) -> list:
    """
    Detect which pages of a PDF are blank (effectively empty / white).

    A page is considered blank when the ratio of near-white pixels exceeds
    *white_pixel_ratio*. "Near-white" means every RGB channel of a pixel is
    at or above *brightness_threshold* (0-255 scale).

    Args:
        pdf_path (str): Path to the PDF file to inspect.
        dpi (int): Resolution used when rasterising each page (default: 150).
            Lower values are faster; higher values catch faint marks more
            reliably.
        brightness_threshold (float): Minimum channel value (0-255) for a
            pixel to be counted as white (default: 253).
        white_pixel_ratio (float): Fraction of pixels that must be white for a
            page to be classified as blank (default: 0.999, i.e. 99.9%).

    Returns:
        list[bool]: A list with one entry per page (in document order).
            ``True`` indicates the page is blank; ``False`` means it contains
            visible content.

    Raises:
        FileNotFoundError: If *pdf_path* does not point to an existing file.

    Examples:
        >>> results = are_pdf_pages_blank("document.pdf")
        >>> for i, blank in enumerate(results, 1):
        ...     print(f"Page {i}: {'blank' if blank else 'has content'}")

        >>> # Stricter detection - flag only completely white pages
        >>> results = are_pdf_pages_blank("document.pdf", white_pixel_ratio=1.0)
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    images = convert_from_path(str(pdf_path), dpi=dpi, fmt="png")

    results = []
    for img in images:
        # Convert to RGB to handle RGBA / palette-mode PDFs uniformly
        rgb = np.array(img.convert("RGB"), dtype=np.float32)
        # A pixel is "white" when all three channels exceed the threshold
        white_mask = np.all(rgb >= brightness_threshold, axis=-1)
        ratio = white_mask.sum() / white_mask.size
        results.append(bool(ratio >= white_pixel_ratio))

    return results


GSPPI_API_URL = "https://gsppi.geniusconsultant.com/GSPPI_API_V2/api/Invoice/GetDigitalInvoice"
GSPPI_BEARER_TOKEN = os.getenv("GSPPI_BEARER_TOKEN", "56dc60de-5d3e-4a1d-84e1-a05fe6a151ce")
GSPPI_SECURITY_CODE = os.getenv("GSPPI_SECURITY_CODE", "888")


def fetch_digital_invoices() -> list:
    """
    Fetch the list of digital invoices from the client's GSPPI API.

    Makes a POST request to the GetDigitalInvoice endpoint using bearer token
    authentication and returns the list of invoice records from Response_Data.

    Returns:
        list: A list of dicts, each containing 'BillID', 'Url', and 'DocType'.

    Raises:
        RuntimeError: If the HTTP request fails or the API returns a non-101
                      response code.

    Example return value:
        [
            {
                "BillID": "GWBIAR/FB0001/26",
                "Url": "https://...pdf",
                "DocType": ""
            },
            ...
        ]
    """
    try:
        response = requests.post(
            GSPPI_API_URL,
            headers={
                "Authorization": f"Bearer {GSPPI_BEARER_TOKEN}",
                "Content-Type": "application/json"
            },
            json={"SecurityCode": GSPPI_SECURITY_CODE},
            timeout=30
        )
        response.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(f"Failed to reach GSPPI API: {e}")

    data = response.json()

    if data.get("Response_Code") != "101":
        raise RuntimeError(
            f"GSPPI API returned an error. "
            f"Code: {data.get('Response_Code')}, "
            f"Message: {data.get('Response_Message')}"
        )

    return data.get("Response_Data", [])


def download_pdf_from_url(url: str) -> str:
    """
    Download a PDF from a URL and save it to a named temporary file.

    The caller is responsible for deleting the temp file after use.

    Args:
        url (str): The direct URL of the PDF file to download.

    Returns:
        str: Absolute path to the saved temporary PDF file.

    Raises:
        ValueError: If the URL is empty or None.
        RuntimeError: If the download fails or the server returns a non-200 status.

    Example:
        >>> path = download_pdf_from_url("https://example.com/invoice.pdf")
        >>> print(path)  # /tmp/tmpXXXXXX.pdf
    """
    if not url:
        raise ValueError("URL must not be empty.")

    try:
        response = requests.get(url, timeout=60)
        response.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(f"Failed to download PDF from '{url}': {e}")

    import tempfile
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(response.content)
        return tmp.name


PROCESSED_LOG_PATH = os.getenv("PROCESSED_LOG_PATH", "processed_invoices.json")


def load_processed_log() -> dict:
    """
    Load the processed invoices log from disk.

    If the log file does not exist yet, an empty dict is returned without
    raising an error — the file will be created on the first write.

    Returns:
        dict: A dict keyed by BillID. Each value is a dict containing at least:
              - 'processed_at' (str): ISO-8601 UTC timestamp
              - 'status' (str): 'success' or 'failed'
              - 'error' (str, optional): Error message if status is 'failed'

    Example:
        {
            "GWBIAR/FB0001/26": {
                "processed_at": "2026-02-20T12:00:00+00:00",
                "status": "success"
            }
        }
    """
    if not os.path.exists(PROCESSED_LOG_PATH):
        return {}

    with open(PROCESSED_LOG_PATH, "r", encoding="utf-8") as f:
        content = f.read().strip()
        if not content:
            return {}
        return json.loads(content)


def update_processed_log(bill_id: str, status: str, url: str = "", doc_type: str = "", error: str = None):
    """
    Append or update a BillID entry in the processed invoices log and write to disk.

    If the BillID already exists in the log (e.g. a previously failed invoice
    that the client has resent), its entry is overwritten with the latest outcome.

    Args:
        bill_id (str): The invoice BillID (e.g. 'GWBIAR/FB0001/26').
        status (str): Outcome of processing — 'success' or 'failed'.
        url (str): The PDF URL for this invoice.
        doc_type (str): The DocType value from the GSPPI API.
        error (str, optional): Error message to record when status is 'failed'.
                               Pass None for successful processing.

    Raises:
        IOError: If the log file cannot be written.
    """
    log = load_processed_log()

    entry = {
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "url": url,
        "doc_type": doc_type
    }
    if error is not None:
        entry["error"] = error

    log[bill_id] = entry

    with open(PROCESSED_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=4, ensure_ascii=False)