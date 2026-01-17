
import frappe
import json

def get_system_context():
    """
    Returns information about the system, installed apps, and versions.
    """
    apps = frappe.get_installed_apps()
    app_info = []
    for app in apps:
        version = frappe.get_attr(f"{app}.__version__") if hasattr(frappe, "get_attr") else "Unknown"
        try:
            import importlib
            module = importlib.import_module(app)
            version = getattr(module, "__version__", "Unknown")
        except:
            version = "Unknown"
        app_info.append(f"{app} ({version})")
    
    return f"""
    System Information:
    - Framework: Frappe / ERPNext
    - Site: {frappe.local.site}
    - Installed Apps: {', '.join(app_info)}
    """

def get_company_context():
    """
    Returns default company details.
    """
    company = frappe.defaults.get_user_default("Company")
    if not company:
        company = frappe.db.get_single_value("Global Defaults", "default_company")
        
    if not company:
        return ""
        
    currency = frappe.db.get_value("Company", company, "default_currency")
    country = frappe.db.get_value("Company", company, "country")
    
    return f"""
    Business Context:
    - Default Company: {company}
    - Currency: {currency}
    - Country: {country}
    """

def get_user_context(user_email=None):
    """
    Returns information about the current user.
    """
    if not user_email:
        user_email = frappe.session.user
        
    if user_email == "Guest":
        return "User: Guest"

    user_doc = frappe.get_doc("User", user_email)
    roles = [r.role for r in user_doc.roles if r.role != "All"]
    
    return f"""
    User Context:
    - User: {user_doc.full_name} ({user_email})
    - Roles: {', '.join(roles[:10])}
    """

def get_route_context(route):
    """
    Analyzes the current frontend route provided by the Bridge.
    Example: '/app/sales-order/NEW-ORDER-1' or '/app/todo'
    """
    if not route: return ""
    
    parts = route.strip("/").split("/")
    
    # Human-readable context
    if len(parts) >= 2 and parts[0] == "app":
        slug = parts[1]
        
        # 1. Try to find DocType
        doctype = None
        # Try direct match or title case
        candidates = [slug, slug.replace("-", " ").title(), slug.title()]
        for c in candidates:
             if frappe.db.exists("DocType", c):
                 doctype = c
                 break
        
        if doctype:
            if len(parts) == 3:
                docname = parts[2]
                if docname.lower() == "new-" + slug:
                     return f"User is creating a new {doctype}."
                return f"User is currently viewing the {doctype}: {docname}."
            elif len(parts) == 2:
                if "report" in slug:
                    return f"User is viewing a Report: {slug}."
                return f"User is viewing the List of {doctype}."

    elif len(parts) >= 1:
        # Generic pages like 'workspace/Home'
        return f"User is currently on the page: {'/'.join(parts)}."

    return f"Current Route: {route}"

def get_common_doctypes():
    """
    Returns a list of commonly used DocTypes.
    """
    common = [
        "User", "ToDo", "File", "Customer", "Item", "Employee", 
        "Sales Order", "Purchase Order", "Sales Invoice", "Purchase Invoice",
        "Quotation", "Supplier", "Company", "Stock Entry", "Delivery Note",
        "OwlAI Agent", "OwlAI Model", "OwlAI Tool", "OwlAI Provider", "OwlAI Settings"
    ]
    return f"Common DocTypes: {', '.join(common)}"

def introspect_doctype(doctype):
    """
    Returns schema info for a DocType to help the Agent understand how to query/create it.
    """
    if not frappe.db.exists("DocType", doctype):
        return None
        
    meta = frappe.get_meta(doctype)
    fields = []
    for f in meta.fields:
        if not f.hidden:
            fields.append(f"{f.fieldname} ({f.fieldtype}) - {f.label}")
            
    return f"""
    DocType Schema: {doctype}
    Description: {meta.description or 'No description'}
    Fields:
    {', '.join(fields[:50])}
    """
