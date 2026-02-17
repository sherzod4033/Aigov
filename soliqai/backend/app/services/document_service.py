import os
import re
import shutil
import uuid
from pathlib import Path
from typing import List

import fitz  # PyMuPDF
from fastapi import UploadFile

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
    MIN_CHUNK_SIZE = 500
    MAX_CHUNK_SIZE = 1000

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
        if content_type and content_type not in allowed_types and content_type not in cls.GENERIC_MIME_TYPES:
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

    @classmethod
    def extract_chunks(cls, file_path: str, extension: str) -> List[dict]:
        if extension == ".pdf":
            return cls.extract_text_from_pdf(file_path)
        if extension == ".docx":
            text = cls.extract_text_from_docx(file_path)
            return cls.semantic_chunk_text(text, page=1)
        if extension == ".txt":
            text = cls.extract_text_from_txt(file_path)
            return cls.semantic_chunk_text(text, page=1)
        raise ValueError("Unsupported file extension")

    @classmethod
    def extract_text_from_pdf(cls, file_path: str) -> List[dict]:
        """
        Extract text from each page and then chunk semantically (500-1000 chars).
        Returns list: {"text": str, "page": int}
        """
        chunks: List[dict] = []
        with fitz.open(file_path) as doc:
            for page_num, page in enumerate(doc):
                page_text = page.get_text()
                if not page_text.strip():
                    continue
                page_chunks = cls.semantic_chunk_text(page_text, page=page_num + 1)
                chunks.extend(page_chunks)
        return chunks

    @staticmethod
    def extract_text_from_docx(file_path: str) -> str:
        try:
            from docx import Document as DocxDocument  # python-docx
        except Exception as exc:
            raise RuntimeError("DOCX support requires python-docx package") from exc

        doc = DocxDocument(file_path)
        paragraphs = [paragraph.text.strip() for paragraph in doc.paragraphs if paragraph.text.strip()]
        return "\n\n".join(paragraphs)

    @staticmethod
    def extract_text_from_txt(file_path: str) -> str:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as file:
            return file.read()

    @classmethod
    def semantic_chunk_text(
        cls,
        text: str,
        page: int,
        min_chars: int | None = None,
        max_chars: int | None = None,
    ) -> List[dict]:
        """
        Semantic chunking by paragraph/sentence with chunk size in [500, 1000] chars.
        """
        min_size = min_chars or cls.MIN_CHUNK_SIZE
        max_size = max_chars or cls.MAX_CHUNK_SIZE

        clean_text = cls._normalize_text(text)
        if not clean_text:
            return []

        segments = cls._split_into_semantic_segments(clean_text)
        chunks: List[dict] = []
        current = ""

        for segment in segments:
            if not segment:
                continue

            # Split oversized segments before adding.
            if len(segment) > max_size:
                for piece in cls._split_long_segment(segment, max_size):
                    chunks, current = cls._append_piece(chunks, current, piece, page, max_size)
                continue

            chunks, current = cls._append_piece(chunks, current, segment, page, max_size)

        if current.strip():
            chunks.append({"text": current.strip(), "page": page})
        return cls._merge_small_chunks(chunks, min_size, max_size)

    @classmethod
    def _append_piece(
        cls,
        chunks: List[dict],
        current: str,
        piece: str,
        page: int,
        max_size: int,
    ) -> tuple[List[dict], str]:
        piece = piece.strip()
        if not piece:
            return chunks, current

        candidate = f"{current}\n\n{piece}".strip() if current else piece

        if len(candidate) <= max_size:
            return chunks, candidate

        if current.strip():
            chunks.append({"text": current.strip(), "page": page})

        # New chunk starts with piece. If piece is still long, split hard.
        if len(piece) <= max_size:
            return chunks, piece

        hard_pieces = cls._hard_split(piece, max_size)
        for hard_piece in hard_pieces[:-1]:
            chunks.append({"text": hard_piece.strip(), "page": page})
        return chunks, hard_pieces[-1].strip()

    @staticmethod
    def _merge_small_chunks(chunks: List[dict], min_size: int, max_size: int) -> List[dict]:
        if not chunks:
            return chunks

        merged: List[dict] = []
        for chunk in chunks:
            if not merged:
                merged.append(chunk)
                continue

            prev = merged[-1]
            same_page = prev.get("page") == chunk.get("page")
            prev_text = (prev.get("text") or "").strip()
            curr_text = (chunk.get("text") or "").strip()
            combined = f"{prev_text}\n\n{curr_text}".strip()

            if same_page and (len(prev_text) < min_size or len(curr_text) < min_size) and len(combined) <= max_size:
                prev["text"] = combined
            else:
                merged.append(chunk)
        return merged

    @staticmethod
    def _normalize_text(text: str) -> str:
        # Keep paragraph boundaries while cleaning repeated spaces.
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        normalized = re.sub(r"[ \t]+", " ", normalized)
        normalized = re.sub(r"\n{3,}", "\n\n", normalized)
        return normalized.strip()

    @staticmethod
    def _split_into_semantic_segments(text: str) -> List[str]:
        # Prefer paragraph chunks; fallback to sentence chunks.
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
        if paragraphs:
            return paragraphs
        return [part.strip() for part in re.split(r"(?<=[.!?։])\s+", text) if part.strip()]

    @classmethod
    def _split_long_segment(cls, text: str, max_size: int) -> List[str]:
        sentence_parts = [part.strip() for part in re.split(r"(?<=[.!?։])\s+", text) if part.strip()]
        if not sentence_parts:
            return cls._hard_split(text, max_size)

        result: List[str] = []
        current = ""
        for sentence in sentence_parts:
            candidate = f"{current} {sentence}".strip() if current else sentence
            if len(candidate) <= max_size:
                current = candidate
            else:
                if current:
                    result.append(current.strip())
                if len(sentence) > max_size:
                    hard = cls._hard_split(sentence, max_size)
                    result.extend(hard[:-1])
                    current = hard[-1]
                else:
                    current = sentence
        if current:
            result.append(current.strip())
        return result

    @staticmethod
    def _hard_split(text: str, max_size: int) -> List[str]:
        return [text[i:i + max_size] for i in range(0, len(text), max_size)]

    @staticmethod
    def is_scanned_pdf(file_path: str) -> bool:
        with fitz.open(file_path) as doc:
            for page in doc:
                if page.get_text().strip():
                    return False
        return True

    @staticmethod
    def detect_language(text: str) -> str:
        sample = (text or "").lower()
        tajik_chars = ("ӯ", "қ", "ҳ", "ҷ", "ғ", "ӣ")
        if any(char in sample for char in tajik_chars):
            return "tj"
        return "ru"
