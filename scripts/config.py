"""Configuration and validation utilities for PDF preprocessor."""

import os

MIN_PDF_SIZE = 10000  # 10KB minimum


def validate_pdf(pdf_path: str) -> tuple:
    """Validate that a PDF file exists and meets minimum size requirements.

    Returns:
        (True, "") if valid, (False, reason) if invalid.
    """
    if not os.path.exists(pdf_path):
        return False, f"File not found: {pdf_path}"
    if not pdf_path.lower().endswith(".pdf"):
        return False, f"Not a PDF file: {pdf_path}"
    size = os.path.getsize(pdf_path)
    if size < MIN_PDF_SIZE:
        return False, f"File too small ({size} bytes): {pdf_path}"
    return True, ""
