
import frappe

def execute():
    # Check Companies
    companies = frappe.get_all("Company", fields=["name", "abbr"])
    print(f"Companies: {companies}")

    # Check for Shareholder Doctype
    shareholder_doctype = frappe.db.exists("DocType", "Shareholder")
    print(f"Shareholder DocType Exists: {shareholder_doctype}")

    # Check for Partner Doctype
    partner_doctype = frappe.db.exists("DocType", "Partner") # Usually referenced in Defaults
    print(f"Partner DocType Exists: {partner_doctype}")

    # Check for Ekansh Jain
    ekansh_cust = frappe.db.get_value("Customer", {"customer_name": "Ekansh Jain"})
    ekansh_supp = frappe.db.get_value("Supplier", {"supplier_name": "Ekansh Jain"})
    print(f"Ekansh Jain - Customer: {ekansh_cust}, Supplier: {ekansh_supp}")

    # Check for Existing Shareholders/Partners
    if shareholder_doctype:
        print("Existing Shareholders:", frappe.get_all("Shareholder", fields=["name"]))
