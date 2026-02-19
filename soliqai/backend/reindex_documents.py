import asyncio
import os
import sys
from sqlmodel import select
from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

# Add backend to path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from app.core.database import engine
from app.models.models import Document, Chunk
from app.services.document_service import DocumentService
from app.services.ocr_service import OCRService
from app.services.rag_service import RAGService

async def reindex_all_documents():
    print("Starting re-indexing process...")
    
    # Create a session manually
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    rag_service = RAGService()
    
    async with async_session() as session:
        # Fetch all documents
        result = await session.exec(select(Document))
        documents = result.all()
        
        print(f"Found {len(documents)} documents to re-index.")
        
        for doc in documents:
            print(f"\nProcessing Document ID: {doc.id} ({doc.name})...")
            
            file_path = doc.path
            if not file_path or not os.path.exists(file_path):
                print(f"  WARNING: File not found at {file_path}. Skipping.")
                continue
                
            # 1. Get existing chunks to delete
            chunks_result = await session.exec(select(Chunk).where(Chunk.doc_id == doc.id))
            existing_chunks = chunks_result.all()
            existing_chunk_ids = [str(c.id) for c in existing_chunks if c.id is not None]
            
            print(f"  Deleting {len(existing_chunks)} existing chunks from DB and Chroma...")
            
            # Delete from Chroma
            try:
                rag_service.delete_documents(existing_chunk_ids)
            except Exception as e:
                print(f"  Error deleting from Chroma: {e}")
            
            # Delete from Postgres
            for chunk in existing_chunks:
                await session.delete(chunk)
            await session.commit()
            
            # 2. Extract new chunks
            print("  Extracting new chunks...")
            file_ext = DocumentService.get_extension(doc.name)
            
            try:
                if file_ext == ".pdf" and DocumentService.is_scanned_pdf(file_path):
                    ocr_pages = OCRService.extract_text_from_scanned_pdf(file_path)
                    chunks_data = []
                    for page_data in ocr_pages:
                        chunks_data.extend(
                            DocumentService.semantic_chunk_text(
                                page_data.get("text", ""),
                                page=page_data.get("page", 1),
                            )
                        )
                else:
                    chunks_data = DocumentService.extract_chunks(file_path, file_ext)
            except Exception as e:
                print(f"  Error extracting text: {e}")
                continue

            if not chunks_data:
                print("  WARNING: No chunks extracted.")
                continue

            print(f"  Generated {len(chunks_data)} new chunks.")
            
            # 3. Save new chunks to Postgres
            new_chunks_objs = []
            docs_text = []
            ids = []
            metadatas = []
            
            for chunk_data in chunks_data:
                chunk = Chunk(
                    text=chunk_data["text"],
                    page=chunk_data["page"],
                    doc_id=doc.id
                )
                session.add(chunk)
                await session.flush() # Populate ID
                await session.refresh(chunk)
                
                new_chunks_objs.append(chunk)
                
                docs_text.append(chunk.text)
                ids.append(str(chunk.id))
                metadatas.append({
                    "doc_id": doc.id, 
                    "doc_name": doc.name, 
                    "page": chunk.page
                })
            
            await session.commit()
            
            # 4. Index in Chroma
            print(f"  Indexing {len(ids)} chunks in ChromaDB...")
            try:
                rag_service.add_documents(docs_text, metadatas, ids)
            except Exception as e:
                print(f"  Error indexing in Chroma: {e}")
            
            print("  Done.")

    print("\nRe-indexing complete.")

if __name__ == "__main__":
    try:
        asyncio.run(reindex_all_documents())
    except Exception as e:
        print(f"Critical error: {e}")
