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
    MIN_CHUNK_SIZE = 200
    MAX_CHUNK_SIZE = 2000
    CHUNK_OVERLAP = 150

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
            return cls.agentic_chunk_text(text, page=1)
        if extension == ".txt":
            text = cls.extract_text_from_txt(file_path)
            return cls.agentic_chunk_text(text, page=1)
        raise ValueError(f"Unsupported file extension: {extension}")

    @classmethod
    def extract_text_from_pdf(cls, file_path: str) -> List[dict]:
        """
        Extract text from each page and then chunk using agentic splitter.
        Returns list: {"text": str, "page": int}
        """
        chunks: List[dict] = []
        with fitz.open(file_path) as doc:
            for page_num, page in enumerate(doc):
                page_text = page.get_text()
                if not page_text.strip():
                    # If page is empty, might be scanned - but detection is separate.
                    # Just skip empty text.
                    continue
                # Use agentic chunking for better semantic boundaries
                page_chunks = cls.agentic_chunk_text(page_text, page=page_num + 1)
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
    def agentic_chunk_text(cls, text: str, page: int) -> List[dict]:
        """
        Agentic chunking using LLM to determine semantic boundaries.
        Falls back to semantic_chunk_text logic if LLM fails or for optimization.
        """
        # Avoid circular import at module level
        from app.services.rag_service import RAGService 
        
        rag_service = RAGService()
        clean_text = cls._normalize_text(text)
        if not clean_text:
            return []
            
        # 1. Split into propositions (sentences)
        # Use simple splitting by punctuation
        propositions = [p.strip() for p in re.split(r"(?<=[.!?։])\s+", clean_text) if p.strip()]
        
        chunks = []
        current_chunk = ""
        
        for prop in propositions:
            # If current chunk is empty, just start with prop
            if not current_chunk:
                current_chunk = prop
                continue
                
            # Hard size limit check - if adding prop exceeds MAX_CHUNK_SIZE, force split
            if len(current_chunk) + len(prop) > cls.MAX_CHUNK_SIZE:
                chunks.append({"text": current_chunk, "page": page})
                current_chunk = prop
                continue
                
            # Optimization: If current chunk is small (<300 chars), merge without asking LLM
            # This reduces LLM calls by ~50% while keeping reasonable minimum context
            if len(current_chunk) < 300:
                current_chunk = f"{current_chunk} {prop}"
                continue

            # Agentic check
            is_new_topic = rag_service.check_semantic_boundary(current_chunk, prop)
            
            if is_new_topic:
                chunks.append({"text": current_chunk, "page": page})
                current_chunk = prop
            else:
                current_chunk = f"{current_chunk} {prop}"
        
        if current_chunk:
            chunks.append({"text": current_chunk, "page": page})
            
        return chunks

    @classmethod
    def semantic_chunk_text(
        cls,
        text: str,
        page: int,
        min_chars: int | None = None,
        max_chars: int | None = None,
    ) -> List[dict]:
        """
        Semantic chunking by paragraph/sentence with chunk size in [MIN_CHUNK_SIZE, MAX_CHUNK_SIZE] chars.
        Adds CHUNK_OVERLAP characters of overlap between consecutive chunks for context continuity.
        """
        min_size = min_chars or cls.MIN_CHUNK_SIZE
        max_size = max_chars or cls.MAX_CHUNK_SIZE

        clean_text = cls._normalize_text(text)
        if not clean_text:
            return []

        segments = cls._split_into_semantic_segments(clean_text)
        chunks: List[dict] = []
        current = ""
        
        # Regex to detect if a segment starts with an Article/Chapter header
        header_pattern = re.compile(r'^(?:СТАТЬЯ|МОДДАИ|БОБИ|ГЛАВА)\s+\d+', re.IGNORECASE)

        for segment in segments:
            if not segment:
                continue
            
            # If current segment is a specific Article/Chapter start, 
            # we should force the previous 'current' to be a chunk (if it exists)
            # so that this Article starts fresh.
            if current and header_pattern.match(segment.strip()):
                chunks.append({"text": current.strip(), "page": page})
                current = ""

            # Split oversized segments before adding.
            if len(segment) > max_size:
                for piece in cls._split_long_segment(segment, max_size):
                    chunks, current = cls._append_piece(chunks, current, piece, page, max_size)
                continue

            chunks, current = cls._append_piece(chunks, current, segment, page, max_size)

        if current.strip():
            chunks.append({"text": current.strip(), "page": page})

        merged = cls._merge_small_chunks(chunks, min_size, max_size)
        return cls._add_overlap(merged, cls.CHUNK_OVERLAP)

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
        
        # Regex to detect if a chunk starts with an Article/Chapter header
        header_pattern = re.compile(r'^(?:СТАТЬЯ|МОДДАИ|БОБИ|ГЛАВА)\s+\d+', re.IGNORECASE)

        for chunk in chunks:
            if not merged:
                merged.append(chunk)
                continue

            prev = merged[-1]
            same_page = prev.get("page") == chunk.get("page")
            prev_text = (prev.get("text") or "").strip()
            curr_text = (chunk.get("text") or "").strip()
            combined = f"{prev_text}\n\n{curr_text}".strip()
            
            # Check if current chunk starts with a header. If so, don't merge it into the previous one,
            # unless the previous one is extremely small (e.g. just a stray character).
            is_header = bool(header_pattern.match(curr_text))
            
            # Force merge if previous is tiny (< 50 chars), likely noise.
            force_merge = len(prev_text) < 50
            
            should_merge = (
                same_page 
                and (len(prev_text) < min_size or len(curr_text) < min_size) 
                and len(combined) <= max_size
            )
            
            if should_merge and (not is_header or force_merge):
                prev["text"] = combined
            else:
                merged.append(chunk)
        return merged

    @staticmethod
    def _normalize_text(text: str) -> str:
        # Keep paragraph boundaries while cleaning repeated spaces.
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        # Fix PDF hyphenation artifacts: "нало-\n гоплательщик" → "налогоплательщик"
        normalized = re.sub(r"-\s*\n\s*", "", normalized)
        # Strip common page number patterns (standalone numbers on their own line)
        normalized = re.sub(r"\n\s*\d{1,3}\s*\n", "\n", normalized)
        normalized = re.sub(r"[ \t]+", " ", normalized)
        normalized = re.sub(r"\n{3,}", "\n\n", normalized)
        return normalized.strip()

    @staticmethod
    def _split_into_semantic_segments(text: str) -> List[str]:
        # 1. Split by "Article" or "Chapter" headers (Russian/Tajik).
        # regex looks for: newline + (СТАТЬЯ|МОДДАИ|БОБИ|ГЛАВА) + space + number
        # We use lookahead (?=...) so the delimiter stays at the start of the new chunk.
        
        # Pattern explanation:
        # \n                  - Start with a newline (ensure it's a header, not inline ref)
        # (?=                 - Positive lookahead (match position, don't consume)
        #   (?:СТАТЬЯ|МОДДАИ|БОБИ|ГЛАВА) - One of these words
        #   \s+               - At least one space
        #   \d+               - A number
        # )
        
        # We assume the text is already normalized (newlines are \n).
        # We prepend a newline to ensuring the first line is matched if it starts with Article.
        dataset = "\n" + text 
        
        # Split using the lookahead pattern
        segments = re.split(r'\n(?=(?:СТАТЬЯ|МОДДАИ|БОБИ|ГЛАВА)\s+\d+)', dataset, flags=re.IGNORECASE)
        
        final_segments = []
        for segment in segments:
            if not segment.strip():
                continue
            
            # If a segment is huge (e.g. intro text before articles), we still might want to split it by paragraphs
            if len(segment) > 2000:
                paragraphs = [p.strip() for p in re.split(r"\n\s*\n", segment) if p.strip()]
                final_segments.extend(paragraphs)
            else:
                final_segments.append(segment.strip())
                
        if final_segments:
            return final_segments

        # Fallback to paragraph chunks
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
        if paragraphs:
            return paragraphs
            
        # Fallback to sentence chunks
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
    def _add_overlap(chunks: List[dict], overlap: int) -> List[dict]:
        """Add overlap between consecutive same-page chunks for context continuity."""
        if not chunks or overlap <= 0:
            return chunks

        result = [chunks[0]]
        for i in range(1, len(chunks)):
            prev_text = (chunks[i - 1].get("text") or "").strip()
            curr_text = (chunks[i].get("text") or "").strip()

            # Only add overlap for chunks on the same page
            if chunks[i].get("page") == chunks[i - 1].get("page") and len(prev_text) > overlap:
                # Take the last `overlap` characters, try to break on a word boundary
                tail = prev_text[-overlap:]
                space_idx = tail.find(" ")
                if space_idx > 0:
                    tail = tail[space_idx + 1:]
                curr_text = f"...{tail}\n\n{curr_text}"

            result.append({"text": curr_text, "page": chunks[i].get("page")})
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
