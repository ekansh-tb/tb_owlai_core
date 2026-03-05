import frappe


def after_install():
    """Called after the app is installed. Full setup: providers, models, agents, tools, bench introspection."""
    try:
        from tb_owlai_core.config.auto_discovery import discover_and_register_providers
        discover_and_register_providers()
        frappe.msgprint("OwlAI: Providers and tools configured.")
    except Exception as e:
        frappe.log_error(f"OwlAI after_install error: {e}", title="OwlAI Setup")

    # Full bench introspection — discovers DocTypes, business domain, builds alias map
    try:
        from tb_owlai_core.intelligence.bench_introspector import full_introspection
        bench_map = full_introspection()
        dt_count = bench_map.get("total_doctypes", 0) if bench_map else 0
        domain = bench_map.get("business_domain", "Unknown") if bench_map else "Unknown"
        frappe.msgprint(f"OwlAI: Bench introspection complete. {dt_count} DocTypes, domain: {domain}")
    except Exception as e:
        frappe.log_error(f"OwlAI bench introspection error: {e}", title="OwlAI Setup")

    # Warm RAG cache if knowledge base has content
    try:
        from tb_owlai_core.intelligence.rag_engine import warm_cache
        warm_cache()
    except Exception as e:
        frappe.log_error(f"OwlAI RAG cache warm error: {e}", title="OwlAI Setup")

    # Ensure an inference model is available (download GGUF in background if needed)
    try:
        frappe.publish_realtime(
            "owlai_setup_progress",
            {"step": "Checking model availability..."},
        )
        frappe.enqueue(
            "tb_owlai_core.intelligence.model_manager.ensure_model_available",
            queue="long",
            timeout=1800,  # 30 min — large GGUF downloads can be slow
        )
    except Exception as e:
        frappe.log_error(f"OwlAI model availability check failed: {e}", title="OwlAI Setup")


def after_migrate():
    """Called on every bench migrate. Must be fast (<2s). Syncs tools + quick bench sync."""
    try:
        from tb_owlai_core.tool_registry import ToolRegistry
        ToolRegistry()
        frappe.logger("owlai").info("OwlAI: Tool sync complete.")
    except Exception as e:
        frappe.log_error(f"OwlAI after_migrate error: {e}", title="OwlAI Migrate")

    # Quick bench sync — only re-scans if DocType count changed (~1s)
    try:
        from tb_owlai_core.intelligence.bench_introspector import quick_sync
        quick_sync()
    except Exception as e:
        frappe.log_error(f"OwlAI bench sync error: {e}", title="OwlAI Migrate")

    # Invalidate dynamic tool cache so it regenerates with fresh metadata
    try:
        from tb_owlai_core.intelligence.tool_factory import invalidate_cache
        invalidate_cache()
    except Exception:
        pass
