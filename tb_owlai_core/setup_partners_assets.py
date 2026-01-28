import frappe
from frappe.utils import flt

def execute():
    company_name = frappe.get_all("Company", limit=1)[0].name
    print(f"Using Company: {company_name}")
    company_abbr = frappe.get_cached_value('Company', company_name, 'abbr')

    # 1. Setup Partners / Shareholders
    partners = ["Narendra Nahata", "Dilip Nahata", "Rahul Nahata", "Shrenik Nahata"]
    
    for partner_name in partners:
        if not frappe.db.exists("Shareholder", {"title": partner_name}):
            print(f"Creating Shareholder: {partner_name}")
            try:
                doc = frappe.get_doc({
                    "doctype": "Shareholder",
                    "title": partner_name,
                    "company": company_name,
                    "shareholding_percentage": 25.0
                })
                doc.insert(ignore_permissions=True)
            except Exception as e:
                print(f"Warning: Could not create Shareholder {partner_name}. It might use a different name field or schema. Error: {e}")
                # Fallback to just check if it exists by some other means or continue
    
    # 2. Setup Capital Accounts (Equity)
    # 2. Setup Capital Accounts (Equity)
    # Find Equity Root or Liability Root (Source of Funds)
    # Roots:
    roots = frappe.get_all("Account", filters={"is_group": 1, "parent_account": "", "company": company_name}, fields=["name", "root_type"])
    print(f"Available Root Accounts: {roots}")

    equity_root_doc = None
    liability_root_doc = None
    
    for r in roots:
        if r.root_type == "Equity":
            equity_root_doc = r
        if r.root_type == "Liability":
            liability_root_doc = r
            
    # Use Equity Root if exists, else Liability Root (Source of Funds)
    parent_root = equity_root_doc if equity_root_doc else liability_root_doc
    if not parent_root:
         # Critical failure if no liability root either
         print("CRITICAL: No Equity OR Liability Root found.")
         return

    print(f"Using Parent for Capital Accounts: {parent_root.name} ({parent_root.root_type})")

    # Ensure 'Capital Accounts' Group Exists
    capital_group_name = "Capital Accounts"
    capital_group = frappe.db.get_value("Account", {"account_name": capital_group_name, "company": company_name})
    
    if not capital_group:
        print(f"Creating Group: {capital_group_name}")
        acc = frappe.get_doc({
            "doctype": "Account",
            "account_name": capital_group_name,
            "company": company_name,
            "parent_account": parent_root.name, 
            "is_group": 1, 
            "account_type": "Equity",
            "root_type": parent_root.root_type # Inherit
        })
        acc.insert(ignore_permissions=True)
        capital_group = acc.name
    
    # Create Individual Partner Accounts
    for partner_name in partners:
        acc_name = f"Capital - {partner_name}"
        if not frappe.db.exists("Account", {"account_name": acc_name, "company": company_name}):
            print(f"Creating Account: {acc_name}")
            acc = frappe.get_doc({
                "doctype": "Account",
                "account_name": acc_name,
                "company": company_name,
                "parent_account": capital_group,
                "is_group": 0,
                "account_type": "Equity",
                "root_type": parent_root.root_type
            })
            acc.insert(ignore_permissions=True)

    # 3. Setup Assets: Investment - Gurukul School
    asset_root_doc = None
    for r in roots:
        if r.root_type == "Asset":
            asset_root_doc = r
            break
    
    if not asset_root_doc:
         # Find legacy asset root
         asset_root_doc = frappe.db.get_value("Account", {"is_group": 1, "root_type": "Asset", "company": company_name}, ["name", "root_type"], as_dict=True)

    asset_root = asset_root_doc.name
    asset_root_type = asset_root_doc.root_type
    print(f"Asset Root: {asset_root} ({asset_root_type})")

    # Create Investments Group if needed
    investments_group_name = "Investments"
    investments_group = frappe.db.get_value("Account", {"account_name": investments_group_name, "company": company_name})
    
    if not investments_group:
         # Check for fixed assets
         fixed_asset_group = frappe.db.get_value("Account", {"account_type": "Fixed Asset", "is_group": 1, "company": company_name})
         parent = fixed_asset_group if fixed_asset_group else asset_root

         print(f"Creating Group: {investments_group_name}")
         acc = frappe.get_doc({
            "doctype": "Account",
            "account_name": investments_group_name,
            "company": company_name,
            "parent_account": parent,
            "is_group": 1,
            "account_type": "Fixed Asset",
            "root_type": asset_root_type
        })
         acc.insert(ignore_permissions=True)
         investments_group = acc.name


    gurukul_acc_name = "Investment - Gurukul School"
    
    if not frappe.db.exists("Account", {"account_name": gurukul_acc_name, "company": company_name}):
        print(f"Creating Account: {gurukul_acc_name}")
        acc = frappe.get_doc({
            "doctype": "Account",
            "account_name": gurukul_acc_name,
            "company": company_name,
            "parent_account": investments_group,
            "is_group": 0,
            "account_type": "Fixed Asset",
            "root_type": asset_root_type
        })
        acc.insert(ignore_permissions=True)
    
    gurukul_acc = frappe.db.get_value("Account", {"account_name": gurukul_acc_name, "company": company_name})

    # 4. Setup Bank Account: Vardhaman Traders
    # Find Bank Accounts group
    bank_group = frappe.db.get_value("Account", {"account_type": "Bank", "is_group": 1, "company": company_name})
    if not bank_group:
         # Create Bank Accounts group if missing
         print("Creating Bank Accounts Group")
         acc = frappe.get_doc({
            "doctype": "Account",
            "account_name": "Bank Accounts",
            "company": company_name,
            "parent_account": asset_root,
            "is_group": 1,
            "account_type": "Bank",
            "root_type": asset_root_type
        })
         acc.insert(ignore_permissions=True)
         bank_group = acc.name

    if not frappe.db.exists("Account", {"account_name": "Vardhaman Traders", "company": company_name}):
        print("Creating Bank Account: Vardhaman Traders")
        acc = frappe.get_doc({
            "doctype": "Account",
            "account_name": "Vardhaman Traders",
            "company": company_name,
            "parent_account": bank_group,
            "is_group": 0,
            "account_type": "Bank",
            "root_type": asset_root_type
        })
        acc.insert(ignore_permissions=True)

    # 5. Create Party: Ekansh Jain (Supplier)
    if not frappe.db.exists("Supplier", "Ekansh Jain"):
        print("Creating Supplier: Ekansh Jain")
        s = frappe.get_doc({
            "doctype": "Supplier",
            "supplier_name": "Ekansh Jain",
            "supplier_group": "Lenders", 
            "company": company_name
        })
        s.insert(ignore_permissions=True)

    # 6. Journal Entry for Gurukul Asset
    temp_account = frappe.db.get_value("Account", {"account_name": "Temporary Opening", "company": company_name})
    # If temp account root type check might change things, but usually it's fine.
    
    amount = 15100000.0 # 1.51 Crore
    remark = "Opening Balance - Investment in Gurukul School"
    
    if not frappe.db.exists("Journal Entry", {"user_remark": remark, "docstatus": 1}):
        print("Creating Journal Entry for Gurukul Asset")
        
        je = frappe.get_doc({
            "doctype": "Journal Entry",
            "posting_date": frappe.utils.nowdate(),
            "company": company_name,
            "user_remark": remark,
            "accounts": [
                {
                    "account": gurukul_acc,
                    "debit_in_account_currency": amount,
                    "credit_in_account_currency": 0
                },
                {
                    "account": temp_account,
                    "credit_in_account_currency": amount,
                    "debit_in_account_currency": 0
                }
            ]
        })
        je.insert(ignore_permissions=True)
        je.submit()
        print(f"Submitted {je.name}")
    else:
        print("Journal Entry for Gurukul already exists.")

    print("Setup Complete.")
