import frappe

def enrich():
    docs = [
        {
            "title": "Frappe Framework Introduction",
            "content": """Frappe is a full stack, batteries-included, web framework written in Python and Javascript with MariaDB as the database. 
            It powers ERPNext and treats meta-data as data, enabling easy UI building. 
            Key features include Role-Based Permissions, REST API for all models, Report Builder, and a built-in Admin Interface (Desk).""",
            "url": "https://docs.frappe.io/framework/user/en/introduction"
        },
        {
            "title": "ERPNext Introduction",
            "content": """ERPNext is business management software tracking inventory, finances, projects, and customers. 
            It is open-source, flexible, and built on the Frappe Framework. 
            Core modules: Assets, Accounting, Inventory, CRM, Payroll, Project Management, and Website publishing.""",
            "url": "https://docs.frappe.io/erpnext/introduction"
        }
    ]
    
    for d in docs:
        if not frappe.db.exists("OwlAI Knowledge Base", {"title": d["title"]}):
            doc = frappe.new_doc("OwlAI Knowledge Base")
            doc.title = d["title"]
            doc.source_type = "Text"
            doc.content = d["content"]
            doc.url = d["url"]
            doc.insert(ignore_permissions=True)
            print(f"Added {d['title']}")
        else:
            print(f"Skipped {d['title']}, already exists")

    frappe.db.commit()

if __name__ == "__main__":
    enrich()
