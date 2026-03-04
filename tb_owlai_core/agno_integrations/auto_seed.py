import frappe


def seed_knowledge_base():
    """
    Scans the current Frappe/ERPNext environment and seeds the Knowledge Base
    with business-specific context and system architecture info.
    """
    try:
        # 1. System Overview
        apps = frappe.get_installed_apps()
        system_info = f"""
System Environment:
- Site: {frappe.local.site}
- Installed Apps: {', '.join(apps)}
- Core DocTypes: {frappe.db.count('DocType')}
- Customizations: {frappe.db.count('Property Setter')} overrides active.
"""
        _add_to_kb("System Overview", system_info, "System")

        # 2. Company Awareness (ERPNext specific)
        if "erpnext" in apps:
            companies = frappe.get_all("Company", fields=["name", "default_currency", "country"])
            for comp in companies:
                comp_info = f"""
Business Entity: {comp.name}
Country: {comp.country}
Currency: {comp.default_currency}
Warehouses: {frappe.db.count('Warehouse', {'company': comp.name})}
Cost Centers: {frappe.db.count('Cost Center', {'company': comp.name})}
"""
                _add_to_kb(f"Business Context: {comp.name}", comp_info, "Business")

            # 3. Product/Service Catalog Summary
            try:
                item_groups = frappe.get_all("Item Group", limit=50)
                catalog_info = "Product Categories: " + ", ".join([ig.name for ig in item_groups])
                _add_to_kb("Product Catalog Summary", catalog_info, "Business")
            except Exception:
                pass

        # 4. User Roles Awareness
        roles = frappe.get_all("Role", limit_page_length=100)
        roles_info = "Available System Roles: " + ", ".join([r.name for r in roles[:50]])
        _add_to_kb("System Permissions/Roles", roles_info, "System")

        return True
    except Exception as e:
        frappe.log_error(f"KB Seeding Failed: {e}")
        return False


def _add_to_kb(title, content, category):
    has_category = frappe.get_meta("OwlAI Knowledge Base").has_field("category")

    if not frappe.db.exists("OwlAI Knowledge Base", {"title": title}):
        doc = frappe.new_doc("OwlAI Knowledge Base")
        doc.title = title
        doc.source_type = "Text"
        doc.content = content
        if has_category:
            doc.category = category
        doc.insert(ignore_permissions=True)
        _try_index(doc)
    else:
        doc = frappe.get_doc("OwlAI Knowledge Base", {"title": title})
        doc.content = content
        if has_category:
            doc.category = category
        doc.save(ignore_permissions=True)
        _try_index(doc)


def _try_index(doc):
    """Attempt vector indexing if lancedb is available."""
    try:
        from tb_owlai_core.agno_integrations.knowledge_index import index_document
        index_document(doc)
        doc.db_set("status", "Indexed")
    except ImportError:
        doc.db_set("status", "Stored")
    except Exception as e:
        frappe.logger("owlai").debug(f"Knowledge indexing skipped: {e}")
        doc.db_set("status", "Stored")
