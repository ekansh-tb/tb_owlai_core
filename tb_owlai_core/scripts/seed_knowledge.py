
import frappe
import os

def seed_knowledge_base():
    """
    Scans installed apps and creates 'OwlAI Knowledge Item' records for:
    1. App READMEs
    2. Module Definitions (high level)
    """
    print("Seeding Knowledge Base...")
    
    apps = frappe.get_installed_apps()
    for app in apps:
        app_path = frappe.get_app_path(app)
        readme_path = os.path.join(os.path.dirname(app_path), "README.md")
        
        content = ""
        if os.path.exists(readme_path):
            with open(readme_path, "r") as f:
                content = f.read()
                
        if content:
            title = f"{app} - Documentation"
            if not frappe.db.exists("OwlAI Knowledge Item", {"title": title}):
                doc = frappe.new_doc("OwlAI Knowledge Item")
                doc.title = title
                doc.content = f"App: {app}\n\n{content}"
                doc.tags = "Documentation, System"
                doc.save(ignore_permissions=True)
                print(f"Created Knowledge Item: {title}")
            else:
                print(f"Knowledge Item exists: {title}")

    # Index common DocTypes
    common_doctypes = ["User", "System Settings", "Company", "Item", "Sales Order", "Customer"]
    for dt in common_doctypes:
        if frappe.db.exists("DocType", dt):
            meta = frappe.get_meta(dt)
            title = f"DocType: {dt}"
            content = f"""
            DocType: {dt}
            Module: {meta.module}
            Description: {meta.description or 'Standard ERPNext Document'}
            
            Key Fields:
            {[f.fieldname for f in meta.fields if not f.hidden][:20]}
            """
            
            if not frappe.db.exists("OwlAI Knowledge Item", {"title": title}):
                doc = frappe.new_doc("OwlAI Knowledge Item")
                doc.title = title
                doc.content = content
                doc.tags = "Schema, Metadata"
                doc.save(ignore_permissions=True)
                print(f"Created Schema Item: {title}")

    frappe.db.commit()
    print("Seeding Complete.")

if __name__ == "__main__":
    seed_knowledge_base()
