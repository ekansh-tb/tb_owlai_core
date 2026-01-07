import frappe
from tb_owlai_core.setup.setup_defaults import setup_all_defaults

def execute():
    """
    Migration script to populate OwlAI data.
    Delegates to setup_defaults.setup_all_defaults() for consistency.
    """
    # Reload doctypes first to ensure schema availability
    frappe.reload_doc("owlai_core", "doctype", "owlai_provider")
    frappe.reload_doc("owlai_core", "doctype", "owlai_model")
    frappe.reload_doc("owlai_core", "doctype", "owlai_tool")
    frappe.reload_doc("owlai_core", "doctype", "owlai_agent")
    frappe.reload_doc("owlai_core", "doctype", "owlai_agent_tool")
    frappe.reload_doc("owlai_core", "doctype", "owlai_settings")

    setup_all_defaults()

