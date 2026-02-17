import asyncio
from sqlmodel import select
from app.core.database import get_session
from app.models.models import Document, FAQ, Chunk
from app.services.rag_service import RAGService

async def check_kb():
    async for session in get_session():
        # Check FAQ
        faq_statement = select(FAQ)
        faq_result = await session.exec(faq_statement)
        faqs = faq_result.all()
        print(f"--- FAQ ({len(faqs)}) ---")
        for faq in faqs[:5]:
            print(f"ID: {faq.id} | Q: {faq.question[:50]}... | A: {faq.answer[:50]}...")
        if len(faqs) > 5:
            print("...")

        # Check Documents
        doc_statement = select(Document)
        doc_result = await session.exec(doc_statement)
        docs = doc_result.all()
        print(f"\n--- Documents ({len(docs)}) ---")
        for doc in docs:
            print(f"ID: {doc.id} | Name: {doc.name} | Status: {doc.status}")

        # Check Chunks
        chunk_statement = select(Chunk)
        chunk_result = await session.exec(chunk_statement)
        chunks = chunk_result.all()
        print(f"\n--- Chunks ({len(chunks)}) ---")
        
    # Check ChromaDB
    try:
        rag = RAGService()
        if rag.collection:
            count = rag.collection.count()
            print(f"\n--- ChromaDB (soliqai_docs) ---")
            print(f"Count: {count}")
            if count > 0:
                peek = rag.collection.peek(limit=1)
                print(f"First ID: {peek['ids'][0]}")
                print(f"First Doc: {peek['documents'][0][:100]}...")
        else:
            print("\n--- ChromaDB ---")
            print("Collection not found or error during init.")
    except Exception as e:
        print(f"\n--- ChromaDB Error ---")
        print(e)

if __name__ == "__main__":
    asyncio.run(check_kb())
