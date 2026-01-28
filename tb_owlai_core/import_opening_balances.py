import frappe
from frappe.utils import flt

def execute():
    # Data from User (Name, Amount in Lakhs)
    # Total should be 305.73 Lakhs
    data = [
        {"name": "Dr Nitin Chacha", "amount_lakhs": 50.00},
        {"name": "Rajendra Bothra", "amount_lakhs": 35.00},
        {"name": "Atul Deshlahra", "amount_lakhs": 14.00},
        {"name": "Dinesh", "amount_lakhs": 10.00},
        {"name": "Dilip tatiya bhila", "amount_lakhs": 10.00},
        {"name": "Sunnyji kukreja", "amount_lakhs": 10.00},
        {"name": "Ashok Gupta", "amount_lakhs": 4.00},
        {"name": "Sbhash Bothra", "amount_lakhs": 6.00},
        {"name": "Suresh Kochar", "amount_lakhs": 6.00},
        {"name": "Anil Ashok", "amount_lakhs": 15.00},
        {"name": "Ajay Bothra", "amount_lakhs": 10.00},
        {"name": "SBI", "amount_lakhs": 10.00},
        {"name": "Doshi", "amount_lakhs": 10.00},
        {"name": "Ramesh Chopda", "amount_lakhs": 52.43},
        {"name": "Virendra Jain", "amount_lakhs": 2.00},
        {"name": "Mandi", "amount_lakhs": 0.80},
        {"name": "Goldy", "amount_lakhs": 25.50},
        {"name": "Rahul's Borrowers", "amount_lakhs": 35.00},
    ]

    # 1. Setup Company and Accounts
    company_name = frappe.get_all("Company", limit=1)[0].name
    print(f"Using Company: {company_name}")

    # Ensure Temporary Opening Account exists
    temp_account = frappe.db.get_value("Account", {"account_name": "Temporary Opening", "company": company_name})
    if not temp_account:
        print("Creating 'Temporary Opening' Account...")
        temp_acc_doc = frappe.get_doc({
            "doctype": "Account",
            "account_name": "Temporary Opening",
            "parent_account": f"Temporary Accounts - {frappe.get_cached_value('Company', company_name, 'abbr')}",
            "company": company_name,
            "is_group": 0,
            "account_type": "Equity" # Usually Equity or Temporary
        })
        # Try to find a root if 'Temporary Accounts' doesn't exist
        if not frappe.db.exists("Account", temp_acc_doc.parent_account):
             # Fallback to Equity root
             root_equity = frappe.db.get_value("Account", {"is_group": 1, "root_type": "Equity", "company": company_name})
             temp_acc_doc.parent_account = root_equity
        
        temp_acc_doc.insert(ignore_permissions=True)
        temp_account = temp_acc_doc.name
    
    print(f"Balancing Account: {temp_account}")

    # Ensure Supplier Group
    supplier_group = "Lenders"
    if not frappe.db.exists("Supplier Group", supplier_group):
        frappe.get_doc({"doctype": "Supplier Group", "supplier_group_name": supplier_group}).insert()

    # 2. Process Data
    total_imported = 0
    
    for item in data:
        amount = flt(item["amount_lakhs"]) * 100000
        party_name = item["name"]

        # 2.1 Ensure Supplier Exists
        if not frappe.db.exists("Supplier", party_name):
            print(f"Creating Supplier: {party_name}")
            s = frappe.get_doc({
                "doctype": "Supplier",
                "supplier_name": party_name,
                "supplier_group": supplier_group,
                "company": company_name
            })
            s.insert(ignore_permissions=True)
        
        # 2.2 Create Journal Entry
        # Check if already exists to avoid duplicates (idempotency)
        # We search for a JE with this specific remark and amount
        remark = f"Opening Balance loan from {party_name}"
        existing_je = frappe.db.get_value("Journal Entry", {"user_remark": remark, "docstatus": 1})

        if existing_je:
            print(f"Skipping {party_name}: Journal Entry {existing_je} already exists.")
            continue

        print(f"Creating Journal Entry for {party_name} ({amount})")
        
        # Get Default Payable Account for Supplier
        payable_account = frappe.get_cached_value("Company", company_name, "default_payable_account")
        if not payable_account:
             # Find any payable account
             payable_account = frappe.db.get_value("Account", {"account_type": "Payable", "company": company_name, "is_group": 0})

        je = frappe.get_doc({
            "doctype": "Journal Entry",
            "posting_date": frappe.utils.nowdate(),
            "company": company_name,
            "user_remark": remark,
            "accounts": [
                {
                    "account": payable_account,
                    "party_type": "Supplier",
                    "party": party_name,
                    "credit_in_account_currency": amount,
                    "debit_in_account_currency": 0
                },
                {
                    "account": temp_account,
                    "debit_in_account_currency": amount,
                    "credit_in_account_currency": 0
                }
            ]
        })
        je.insert(ignore_permissions=True)
        je.submit()
        print(f"Submitted {je.name}")
        total_imported += amount

    print(f"Total Imported Liability: {total_imported} (Expect {305.73 * 100000})")

