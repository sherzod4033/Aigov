import pytesseract
from pdf2image import convert_from_path
import os
from typing import List

class OCRService:
    @staticmethod
    def extract_text_from_scanned_pdf(file_path: str, lang: str = "rus+tgk") -> List[dict]:
        """
        Converts PDF pages to images and runs Tesseract OCR.
        Requires 'poppler-utils' installed on the system.
        """
        try:
            images = convert_from_path(file_path)
            chunks = []
            for i, image in enumerate(images):
                text = pytesseract.image_to_string(image, lang=lang)
                if text.strip():
                    chunks.append({"text": text, "page": i + 1})
            return chunks
        except Exception as e:
            print(f"OCR Error: {e}")
            return []
