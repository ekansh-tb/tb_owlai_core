from tb_owlai_core.plugins.base import BasePlugin

class CorePlugin(BasePlugin):
    """
    Core plugin that provides essential Frappe document and system operations.
    This plugin is always enabled and contains tools for the internal assistant.
    """

    def get_info(self):
        return {
            "name": "core",
            "display_name": "Core Operations",
            "description": "Essential Frappe document operations, search, metadata, and reporting tools. Optimized for internal Chat Assistant.",
            "version": "1.0.0",
            "dependencies": [],
            "requires_restart": False,
            "always_enabled": True, 
        }

    def get_tools(self):
        """
        Return list of core tool module names.
        """
        return [
            # CRUD
            "create_document",
            "get_document",
            "update_document",
            "delete_document",
            
            # List & Search (Enhanced with filters)
            "list_documents",
            "search_documents",
            
            # Bulk
            # "bulk_create_documents", # TODO: Phase 2
            
            # Metadata
            "get_doctype_info",
            
            # Reporting
            "generate_report",
            # "report_list", # TODO: Phase 2
            
            # Workflow
            "run_workflow",
        ]

    def validate_environment(self):
        return True, None

    def on_enable(self):
        self.logger.info("Core plugin enabled")

    def get_capabilities(self):
        return {
            "document_operations": True,
            "search": True,
            "metadata": True,
            "reporting": True
        }
