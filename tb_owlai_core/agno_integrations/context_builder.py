
import frappe
import json

def get_system_context():
    """
    Returns information about the system, installed apps, and versions.
    """
    apps = frappe.get_installed_apps()
    app_info = []
    for app in apps:
        version = frappe.get_attr(f"{app}.__version__") if hasattr(frappe, "get_attr") else "Unknown" # simplified
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
        # Try to find a default company
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
    Analyzes the current frontend route to provide specific guidance.
    """
    if not route:
        return ""
        
    # Example routes:
    # /app/todo
    # /app/sales-order/new-sales-order-1
    # /app/dashboard-view/Sales
    
    context = []
    context.append(f"Current Page/Route: {route}")
    
    parts = route.strip("/").split("/")
    if len(parts) >= 2 and parts[0] == "app":
        doctype_slug = parts[1]
        # heuristics to guess doctype from slug i.e. sales-order -> Sales Order
        # This is not perfect but helpful
        pass 
        
    return "\n".join(context)

def get_common_doctypes():
    """
    Returns a list of commonly used DocTypes to help the model not hallucinate names.
    """
    # This list could be dynamic based on usage or static top 20
    common = [
        "User", "ToDo", "File", "Customer", "Item", "Employee", 
        "Sales Order", "Purchase Order", "Sales Invoice", "Purchase Invoice",
        "Quotation", "Supplier", "Company",
        "OwlAI Agent", "OwlAI Model", "OwlAI Tool", "OwlAI Provider", "OwlAI Settings"
    ]
    return f"Common DocTypes: {', '.join(common)}"
