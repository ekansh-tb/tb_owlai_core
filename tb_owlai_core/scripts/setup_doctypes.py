
import frappe

def create_doctypes():
    # 1. OwlAI User Memory
    if not frappe.db.exists("DocType", "OwlAI User Memory"):
        doc = frappe.get_doc({
            "doctype": "DocType",
            "module": "OwlAI Core",
            "name": "OwlAI User Memory",
            "custom": 1,
            "fields": [
                {"fieldname": "user", "fieldtype": "Link", "options": "User", "label": "User", "reqd": 1, "in_list_view": 1},
                {"fieldname": "memory_type", "fieldtype": "Select", "options": "User Preference\nFact\nSummary", "label": "Type", "default": "Fact"},
                {"fieldname": "topic", "fieldtype": "Data", "label": "Topic"},
                {"fieldname": "content", "fieldtype": "Text", "label": "Content", "reqd": 1},
                {"fieldname": "embedding", "fieldtype": "Code", "label": "Embedding (Vector)", "hidden": 1} # Placeholder for now
            ],
            "permissions": [{"role": "System Manager", "read": 1, "write": 1}]
        })
        doc.insert()
        print("Created DocType: OwlAI User Memory")
    else:
        print("OwlAI User Memory already exists.")

    # 2. OwlAI Knowledge Item
    if not frappe.db.exists("DocType", "OwlAI Knowledge Item"):
        doc = frappe.get_doc({
            "doctype": "DocType",
            "module": "OwlAI Core",
            "name": "OwlAI Knowledge Item",
            "custom": 1,
            "fields": [
                {"fieldname": "title", "fieldtype": "Data", "label": "Title", "reqd": 1, "in_list_view": 1},
                {"fieldname": "source_doctype", "fieldtype": "Link", "options": "DocType", "label": "Source DocType"},
                {"fieldname": "source_name", "fieldtype": "Dynamic Link", "options": "source_doctype", "label": "Source Record"},
                {"fieldname": "content", "fieldtype": "Text Editor", "label": "Content (Markdown)", "reqd": 1},
                {"fieldname": "tags", "fieldtype": "Data", "label": "Tags"},
                {"fieldname": "is_vectorized", "fieldtype": "Check", "label": "Is Vectorized", "default": 0}
            ],
            "permissions": [{"role": "System Manager", "read": 1, "write": 1}]
        })
        doc.insert()
        print("Created DocType: OwlAI Knowledge Item")
    else:
        print("OwlAI Knowledge Item already exists.")

    frappe.db.commit()

if __name__ == "__main__":
    create_doctypes()
