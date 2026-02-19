"""
Document Service — unified extraction pipeline.

All document types (PDF, DOCX, TXT) are converted to TextBlock objects,
then chunked with HybridChunker. No more dual-path agentic/semantic branching.
"""

import os
import re
import shutil
import uuid
from pathlib import Path
from typing import List

import fitz  # PyMuPDF
from fastapi import UploadFile

from app.services.hybrid_chunker import TextBlock, ChunkResult, HybridChunker
from app.services.ocr_service import OCRService

UPLOAD_DIR = "data/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


class DocumentService:
    ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
    GENERIC_MIME_TYPES = {"application/octet-stream", "binary/octet-stream"}
    MIME_BY_EXTENSION = {
        ".pdf": {"application/pdf"},
        ".docx": {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/zip",
        },
        ".txt": {"text/plain"},
    }

    @staticmethod
    def get_extension(filename: str) -> str:
        return Path(filename).suffix.lower()

    @classmethod
    def validate_upload_file(cls, upload_file: UploadFile) -> str:
        if not upload_file.filename:
            raise ValueError("Filename is required")

        ext = cls.get_extension(upload_file.filename)
        if ext not in cls.ALLOWED_EXTENSIONS:
            raise ValueError("Unsupported file type. Allowed: PDF, DOCX, TXT")

        content_type = (upload_file.content_type or "").lower()
        allowed_types = cls.MIME_BY_EXTENSION.get(ext, set())
        if (
            content_type
            and content_type not in allowed_types
            and content_type not in cls.GENERIC_MIME_TYPES
        ):
            raise ValueError(
                f"Invalid content type '{upload_file.content_type}' for extension '{ext}'"
            )
        return ext

    @staticmethod
    async def save_upload_file(upload_file: UploadFile) -> str:
        safe_name = Path(upload_file.filename or "document").name
        file_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex}_{safe_name}")
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(upload_file.file, buffer)
        return file_path

    # ------------------------------------------------------------------
    # Unified extraction: any document → TextBlock[]
    # ------------------------------------------------------------------

    @classmethod
    def extract_blocks(cls, file_path: str, extension: str) -> List[TextBlock]:
        """
        Extract TextBlocks from any supported document type.

        PDF: per-page extraction with automatic OCR fallback for sparse pages.
        DOCX: paragraphs → TextBlocks.
        TXT: paragraph-split → TextBlocks.
        """
        if extension == ".pdf":
            return cls._extract_blocks_from_pdf(file_path)
        if extension == ".docx":
            return cls._extract_blocks_from_docx(file_path)
        if extension == ".txt":
            return cls._extract_blocks_from_txt(file_path)
        raise ValueError(f"Unsupported file extension: {extension}")

    @classmethod
    def extract_and_chunk(
        cls,
        file_path: str,
        extension: str,
        chunker: HybridChunker | None = None,
    ) -> List[ChunkResult]:
        """
        Full pipeline: extract blocks → chunk.
        Convenience method for callers that want chunks directly.
        """
        blocks = cls.extract_blocks(file_path, extension)
        if not blocks:
            return []
        if chunker is None:
            chunker = HybridChunker()
        return chunker.chunk(blocks)

    # ------------------------------------------------------------------
    # PDF extraction (per-page, with mixed OCR support)
    # ------------------------------------------------------------------

    @classmethod
    def _extract_blocks_from_pdf(cls, file_path: str) -> List[TextBlock]:
        """
        Extract text from PDF using PyMuPDF blocks API.
        Falls back to OCR per-page when text layer is insufficient.
        """
        blocks: List[TextBlock] = []
        order = 0

        with fitz.open(file_path) as doc:
            for page_num, page in enumerate(doc, start=1):
                # Try text layer first using blocks API for better structure
                page_blocks = page.get_text("blocks")  # (x0, y0, x1, y1, text, block_no, block_type)

                # Collect text from text blocks (block_type 0 = text)
                text_content = []
                block_infos = []
                for b in page_blocks:
                    if b[6] == 0:  # text block
                        text = b[4].strip()
                        if text:
                            text_content.append(text)
                            block_infos.append(b)

                page_text = "\n".join(text_content)

                # Check if this page needs OCR
                if OCRService.page_needs_ocr(page_text):
                    # OCR fallback for this specific page
                    ocr_text = OCRService.ocr_single_page(file_path, page_num)
                    if ocr_text.strip():
                        blocks.append(TextBlock(
                            text=ocr_text,
                            page=page_num,
                            order=order,
                            source="ocr",
                        ))
                        order += 1
                    continue

                # Add each text block separately (preserves structure)
                for b in block_infos:
                    text = b[4].strip()
                    if text:
                        blocks.append(TextBlock(
                            text=text,
                            page=page_num,
                            order=order,
                            bbox=(b[0], b[1], b[2], b[3]),
                            source="pymupdf",
                        ))
                        order += 1

        return blocks

    # ------------------------------------------------------------------
    # DOCX extraction
    # ------------------------------------------------------------------

    @classmethod
    def _extract_blocks_from_docx(cls, file_path: str) -> List[TextBlock]:
        """Extract paragraphs from DOCX as TextBlocks."""
        try:
            from docx import Document as DocxDocument
        except Exception as exc:
            raise RuntimeError("DOCX support requires python-docx package") from exc

        doc = DocxDocument(file_path)
        blocks: List[TextBlock] = []

        for i, paragraph in enumerate(doc.paragraphs):
            text = paragraph.text.strip()
            if text:
                blocks.append(TextBlock(
                    text=text,
                    page=1,  # DOCX doesn't have page numbers
                    order=i,
                    source="docx",
                ))

        return blocks

    # ------------------------------------------------------------------
    # TXT extraction
    # ------------------------------------------------------------------

    @classmethod
    def _extract_blocks_from_txt(cls, file_path: str) -> List[TextBlock]:
        """Read TXT file, split by double newlines into TextBlocks."""
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        paragraphs = re.split(r"\n\s*\n", content)
        blocks: List[TextBlock] = []

        for i, para in enumerate(paragraphs):
            text = para.strip()
            if text:
                blocks.append(TextBlock(
                    text=text,
                    page=1,
                    order=i,
                    source="txt",
                ))

        return blocks

    # ------------------------------------------------------------------
    # Helpers (kept from original)
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_text(text: str) -> str:
        """Normalize text (kept for backward compatibility)."""
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        normalized = re.sub(r"-\s*\n\s*", "", normalized)
        normalized = re.sub(r"\n\s*\d{1,3}\s*\n", "\n", normalized)
        normalized = re.sub(r"[ \t]+", " ", normalized)
        normalized = re.sub(r"\n{3,}", "\n\n", normalized)
        return normalized.strip()

    @staticmethod
    def detect_language(text: str) -> str:
        sample = (text or "").lower()
        tajik_chars = ("ӯ", "қ", "ҳ", "ҷ", "ғ", "ӣ")
        if any(char in sample for char in tajik_chars):
            return "tj"
        return "ru"
