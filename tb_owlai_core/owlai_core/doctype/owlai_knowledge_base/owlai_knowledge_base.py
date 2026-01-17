# Copyright (c) 2024, TechBirdIt.in and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from tb_owlai_core.agno_integrations.knowledge_index import index_document, delete_from_index

class OwlAIKnowledgeBase(Document):
    def validate(self):
        if self.source_type == "URL" and not self.url:
            frappe.throw("URL is required for Source Type 'URL'")
        if self.source_type == "File" and not self.file:
            frappe.throw("File is required for Source Type 'File'")

    def before_save(self):
        # if self.is_new():
        #     self.status = "Pending"
        self.status = "Pending"
            
    def on_update(self):
        doc_before_save = self.get_doc_before_save()
        if not doc_before_save:
            return

        # Check if content-related fields have changed
        content_changed = (
            self.source_type != doc_before_save.source_type or
            (self.source_type == "Text" and self.content != doc_before_save.content) or
            (self.source_type == "URL" and self.url != doc_before_save.url) or
            (self.source_type == "File" and self.file != doc_before_save.file)
        )

        if content_changed:
            self.status = "Pending"
            frappe.enqueue(
                'tb_owlai_core.owlai_core.doctype.owlai_knowledge_base.owlai_knowledge_base.add_to_index',
                queue='long',
                doc_name=self.name,
                job_name=f"reindex-{self.name}" # Give job a name to avoid duplicates
            )

    def after_insert(self):
        # Trigger indexing in background
        frappe.enqueue(
            'tb_owlai_core.owlai_core.doctype.owlai_knowledge_base.owlai_knowledge_base.add_to_index',
            queue='long',
            doc_name=self.name,
            job_name=f"index-{self.name}"
        )
        
    def on_trash(self):
        # Trigger delete from index in background
        frappe.enqueue(
            'tb_owlai_core.owlai_core.doctype.owlai_knowledge_base.owlai_knowledge_base.remove_from_index',
            queue='long',
            doc_name=self.name,
            job_name=f"unindex-{self.name}"
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
        
@frappe.whitelist()
def remove_from_index(doc_name):
    """
    Background Task to remove the document from the index.
    """
    try:
        delete_from_index(doc_name)
    except Exception as e:
        frappe.log_error(f"Knowledge Base Deletion Error: {e}")
