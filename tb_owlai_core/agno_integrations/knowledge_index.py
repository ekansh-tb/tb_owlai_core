
import frappe
import os
import shutil
from typing import List, Dict, Any

try:
    from agno.vectordb.lancedb import LanceDb
    from agno.knowledge.embedder.ollama import OllamaEmbedder
    # from agno.document import Document as AgnoDocument # Old path
    from agno.knowledge.document.base import Document as AgnoDocument
    # from agno.utils.text import clean_text # Not found easily, we will inline or skip
except ImportError as e:
    frappe.log_error(f"Agno or LanceDB not installed. RAG features will be disabled. Error: {e}")

def clean_text(text):
    """Simple text cleaner if agno utils is missing"""
    import re
    if not text: return ""
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def get_vector_db():
    """
    Returns the configured LanceDB instance.
    Uses 'nomic-embed-text' by default, customizable via settings.
    """
    settings = frappe.get_single("OwlAI Settings")
    model_name = getattr(settings, "embedding_model", "nomic-embed-text")
    
    # Path to store vector db
    bench_path = frappe.utils.get_bench_path()
    site_path = frappe.get_site_path()
    db_path = os.path.join(site_path, "private", "owlai_lancedb")
    
    embedder = OllamaEmbedder(id=model_name)
    
    vector_db = LanceDb(
        table_name="owlai_knowledge",
        uri=db_path,
        embedder=embedder,
        search_type="hybrid" # Hybrid requires tantivy, fallback to vector if fails? 
        # For simplicity, let's stick to default or vector unless sure about tantivy
    )
    return vector_db

def index_document(doc):
    """
    Indexes a Frappe 'OwlAI Knowledge Base' document into LanceDB.
    Returns: {"chunks": int, "vector_id": str}
    """
    try:
        vector_db = get_vector_db()
        
        # 1. Extract Text
        text_content = ""
        if doc.source_type == "Text":
            text_content = doc.content
            
        elif doc.source_type == "URL":
            # Simple fetch for now, can upgrade to Firecrawl/Agno WebsiteReader
            import requests
            from bs4 import BeautifulSoup
            try:
                res = requests.get(doc.url, timeout=10)
                soup = BeautifulSoup(res.content, "html.parser")
                # Remove script and style elements
                for script in soup(["script", "style"]):
                    script.extract()
                text_content = soup.get_text()
            except Exception as e:
                raise Exception(f"Failed to fetch URL: {e}")
                
        elif doc.source_type == "File":
            # Handle Text/PDF files
            file_path = frappe.get_site_path(doc.file.lstrip("/"))
            if doc.file.endswith(".pdf"):
                try:
                    from pypdf import PdfReader
                    reader = PdfReader(file_path)
                    for page in reader.pages:
                        text_content += page.extract_text() + "\n"
                except ImportError:
                     raise Exception("pypdf not installed. Please install it to index PDFs.")
            else:
                # Assume text
                with open(file_path, "r") as f:
                    text_content = f.read()

        text_content = clean_text(text_content)
        if not text_content:
            raise Exception("No content extracted to index.")

        # 2. Create Agno Documents (Chunks)
        # We manually chunk or let VectorDB handle it? 
        # LanceDB's upsert in Agno usually expects Agno Documents
        
        from agno.knowledge.chunking.recursive import RecursiveChunking
        
        # Create base document first
        base_doc = AgnoDocument(
            content=text_content,
            meta_data={
                "doc_name": doc.name,
                "title": doc.title,
                "source": doc.source_type,
                "url": doc.url,
            }
        )

        chunker = RecursiveChunking(chunk_size=1000, overlap=100)
        igno_docs = chunker.chunk(base_doc)
            
        # 3. Upsert
        # Check if table exists, create if not
        # LanceDB in Agno handles this automatically usually on insert
        vector_db.create() # Idempotent?
        vector_db.upsert(igno_docs)
        
        return {
            "chunks": len(igno_docs),
            "vector_id": doc.name # We index by metadata, not single ID
        }

    except Exception as e:
        frappe.log_error(f"Index Error: {e}")
        raise e

def search_knowledge_base(query: str, limit: int = 5):
    """
    Searches the Knowledge Base.
    """
    try:
        vector_db = get_vector_db()
        results = vector_db.search(query, limit=limit)
        
        # Format results
        hits = []
        for r in results:
             hits.append({
                 "content": r.content,
                 "meta": r.meta_data,
                 "score": r.score
             })
        return hits
    except Exception as e:
        frappe.log_error(f"Search Error: {e}")
        return []
