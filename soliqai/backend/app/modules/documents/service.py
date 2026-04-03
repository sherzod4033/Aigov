import os
from typing import Any, Optional

from fastapi import HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.models import Chunk, Document, Notebook
from app.services.hybrid_chunker import HybridChunker
from app.services.source_service import SourceService
from app.modules.rag.service import RAGService


class DocumentModuleService:
    @staticmethod
    async def upload_document(
        session: AsyncSession, file: UploadFile, notebook_id: Optional[int] = None
    ) -> Document:
        try:
            file_ext = SourceService.validate_upload_file(file)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        notebook: Notebook | None = None
        if notebook_id is not None:
            notebook = await session.get(Notebook, notebook_id)
            if not notebook:
                raise HTTPException(status_code=404, detail="Notebook not found")

        file_path = await SourceService.save_upload_file(file)
        chunker = HybridChunker()
        chunk_results = await run_in_threadpool(
            SourceService.extract_and_chunk, file_path, file_ext, chunker
        )
        if not chunk_results:
            if os.path.exists(file_path):
                os.remove(file_path)
            raise HTTPException(
                status_code=400, detail="Could not extract text from file"
            )

        sample_text = " ".join(cr.text for cr in chunk_results[:5])
        detected_language = SourceService.detect_language(sample_text)
        actual_size = os.path.getsize(file_path)
        doc = Document(
            name=file.filename,
            path=file_path,
            size=actual_size,
            language=detected_language,
            status="indexed",
            notebook_id=notebook.id if notebook else None,
        )
        session.add(doc)
        await session.commit()
        await session.refresh(doc)

        rag_service = RAGService()
        docs_text: list[str] = []
        ids: list[str] = []
        metadatas: list[dict[str, Any]] = []
        for cr in chunk_results:
            chunk = Chunk(
                text=cr.text,
                page=cr.page_start,
                chunk_index=cr.chunk_index,
                section=cr.section_path_json if cr.section_path else None,
                doc_id=doc.id,
            )
            session.add(chunk)
            await session.flush()
            docs_text.append(chunk.text)
            ids.append(str(chunk.id))
            metadatas.append(
                {
                    "doc_id": doc.id,
                    "doc_name": doc.name,
                    "page": chunk.page,
                    "chunk_index": cr.chunk_index,
                    "notebook_id": doc.notebook_id,
                }
            )
        await session.commit()
        try:
            rag_service.add_documents(docs_text, metadatas, ids)
        except Exception as exc:
            doc.status = "error"
            session.add(doc)
            await session.commit()
            raise HTTPException(
                status_code=503,
                detail="Document saved, but indexing failed: ChromaDB is unavailable.",
            ) from exc
        return doc

    @staticmethod
    async def read_documents(
        session: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        notebook_id: int | None = None,
    ):
        statement = select(Document)
        if notebook_id is not None:
            statement = statement.where(Document.notebook_id == notebook_id)
        result = await session.exec(statement.offset(skip).limit(limit))
        return result.all()

    @staticmethod
    async def get_document_chunks(session: AsyncSession, document_id: int):
        doc = await session.get(Document, document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        result = await session.exec(
            select(Chunk).where(Chunk.doc_id == document_id).order_by(Chunk.chunk_index)
        )
        return result.all()

    @staticmethod
    async def delete_document(session: AsyncSession, document_id: int) -> Document:
        doc = await session.get(Document, document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        chunks_result = await session.exec(
            select(Chunk).where(Chunk.doc_id == document_id)
        )
        chunks = chunks_result.all()
        chunk_ids = [str(chunk.id) for chunk in chunks if chunk.id is not None]
        rag_service = RAGService()
        try:
            rag_service.delete_documents(chunk_ids)
        except Exception as exc:
            raise HTTPException(
                status_code=503, detail="Failed to delete embeddings from ChromaDB."
            ) from exc
        if doc.path and os.path.exists(doc.path):
            try:
                os.remove(doc.path)
            except OSError as exc:
                raise HTTPException(
                    status_code=500, detail="Failed to delete document file from disk."
                ) from exc
        for chunk in chunks:
            await session.delete(chunk)
        await session.delete(doc)
        await session.commit()
        return doc

    @staticmethod
    async def reindex_all_documents(session: AsyncSession) -> dict[str, Any]:
        import logging

        logger = logging.getLogger(__name__)
        result = await session.exec(select(Document))
        documents = result.all()
        if not documents:
            return {
                "status": "ok",
                "message": "No documents to reindex",
                "total_chunks": 0,
            }
        rag_service = RAGService()
        chunker = HybridChunker()
        all_chunks_result = await session.exec(select(Chunk))
        all_chunks = all_chunks_result.all()
        old_chunk_ids = [str(c.id) for c in all_chunks if c.id is not None]
        if old_chunk_ids:
            try:
                rag_service.delete_documents(old_chunk_ids)
            except Exception:
                logger.warning("Could not delete old chunks from ChromaDB")
        for chunk in all_chunks:
            await session.delete(chunk)
        await session.flush()
        total_chunks = 0
        errors: list[str] = []
        for doc in documents:
            try:
                if not doc.path or not os.path.exists(doc.path):
                    errors.append(f"File missing for document {doc.id}: {doc.name}")
                    doc.status = "error"
                    session.add(doc)
                    continue
                ext = SourceService.get_extension(doc.name or doc.path)
                chunk_results = await run_in_threadpool(
                    SourceService.extract_and_chunk, doc.path, ext, chunker
                )
                if not chunk_results:
                    errors.append(
                        f"No text extracted from document {doc.id}: {doc.name}"
                    )
                    doc.status = "error"
                    session.add(doc)
                    continue
                docs_text: list[str] = []
                ids: list[str] = []
                metadatas: list[dict[str, Any]] = []
                for cr in chunk_results:
                    chunk = Chunk(
                        text=cr.text,
                        page=cr.page_start,
                        chunk_index=cr.chunk_index,
                        section=cr.section_path_json if cr.section_path else None,
                        doc_id=doc.id,
                    )
                    session.add(chunk)
                    await session.flush()
                    docs_text.append(chunk.text)
                    ids.append(str(chunk.id))
                    metadatas.append(
                        {
                            "doc_id": doc.id,
                            "doc_name": doc.name,
                            "page": chunk.page,
                            "chunk_index": cr.chunk_index,
                            "notebook_id": doc.notebook_id,
                        }
                    )
                rag_service.add_documents(docs_text, metadatas, ids)
                doc.status = "indexed"
                session.add(doc)
                total_chunks += len(chunk_results)
                logger.info(
                    f"Reindexed doc {doc.id} ({doc.name}): {len(chunk_results)} chunks"
                )
            except Exception as exc:
                errors.append(f"Error reindexing doc {doc.id} ({doc.name}): {str(exc)}")
                doc.status = "error"
                session.add(doc)
        await session.commit()
        return {
            "status": "ok" if not errors else "partial",
            "total_documents": len(documents),
            "total_chunks": total_chunks,
            "errors": errors,
        }
