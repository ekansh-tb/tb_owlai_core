# Copyright (c) 2024, TechBirdIt.in and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from tb_owlai_core.agno_integrations.knowledge_index import index_document

class OwlAIKnowledgeBase(Document):
    def validate(self):
        if self.source_type == "URL" and not self.url:
            frappe.throw("URL is required for Source Type 'URL'")
        if self.source_type == "File" and not self.file:
            frappe.throw("File is required for Source Type 'File'")
            
    def before_save(self):
        if self.is_new():
            self.status = "Pending"
            
    def after_insert(self):
        # Trigger indexing in background
        frappe.enqueue(
            'tb_owlai_core.owlai_core.doctype.owlai_knowledge_base.owlai_knowledge_base.add_to_index',
            queue='long',
            doc_name=self.name
        )

@frappe.whitelist()
def add_to_index(doc_name):
    """
    Background Task to index the document.
    """
    doc = frappe.get_doc("OwlAI Knowledge Base", doc_name)
    try:
        doc.db_set("status", "Indexing")
        
        # Call the Agno/RAG logic
        result = index_document(doc)
        
        doc.db_set("status", "Indexed")
        doc.db_set("chunk_count", result.get("chunks", 0))
        doc.db_set("vector_id", result.get("vector_id"))
        doc.db_set("error", "")
        
    except Exception as e:
        frappe.log_error(f"Knowledge Base Indexing Error: {e}")
        doc.db_set("status", "Failed")
        doc.db_set("error", str(e))
