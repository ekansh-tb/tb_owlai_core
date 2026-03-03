import frappe


def after_install():
    """Called after the app is installed. Full setup: providers, models, agents, tools."""
    try:
        from tb_owlai_core.config.auto_discovery import discover_and_register_providers
        discover_and_register_providers()
        frappe.msgprint("OwlAI: Setup complete. Providers and tools configured.")
    except Exception as e:
        frappe.log_error(f"OwlAI after_install error: {e}", title="OwlAI Setup")


def after_migrate():
    """Called on every bench migrate. Must be fast (<2s). Only syncs tools."""
    try:
        from tb_owlai_core.tool_registry import ToolRegistry
        ToolRegistry()
        frappe.logger("owlai").info("OwlAI: Tool sync complete.")
    except Exception as e:
        frappe.log_error(f"OwlAI after_migrate error: {e}", title="OwlAI Migrate")
