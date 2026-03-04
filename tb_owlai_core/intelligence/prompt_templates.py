"""
Prompt Templates - Multi-step action examples and system prompt components for OwlAI.
"""

MULTI_STEP_EXAMPLES = """
## Multi-Step Action Examples

These examples show how to chain tool calls to complete complex requests. Always resolve
entities (customers, items, suppliers) before creating or referencing documents.

---

### Example 1: Create Sales Order for a customer and item (English)
User: "Create SO for Ram for Saree"

Step 1 -> search_documents(doctype="Customer", search_term="Ram")
Result: [{"name": "Ram Traders", "customer_name": "Ram Traders"}]

Step 2 -> search_documents(doctype="Item", search_term="Saree")
Result: [{"name": "ITEM-SAREE-001", "item_name": "Banarasi Saree"}]

Step 3 -> create_document(doctype="Sales Order", data={
  "customer": "Ram Traders",
  "items": [{"item_code": "ITEM-SAREE-001", "qty": 1}]
})
Result: Sales Order SO-2024-00123 created successfully.

Response: "Created Sales Order SO-2024-00123 for Ram Traders with 1x Banarasi Saree."

---

### Example 2: Check outstanding balance for a party (English)
User: "How much does Shyam owe us?"

Step 1 -> search_documents(doctype="Customer", search_term="Shyam")
Result: [{"name": "Shyam Enterprises", "customer_name": "Shyam Enterprises"}]

Step 2 -> get_party_outstanding(party="Shyam Enterprises", party_type="Customer")
Result: {"outstanding": 45000.0, "currency": "INR"}

Response: "Shyam Enterprises owes 45,000. Would you like to create a payment reminder?"

---

### Example 3: Hinglish - Create purchase order
User: "Mohan ke liye purchase order banao, 50 kg chawal"

Step 1 -> search_documents(doctype="Supplier", search_term="Mohan")
Result: [{"name": "Mohan Rice Mills", "supplier_name": "Mohan Rice Mills"}]

Step 2 -> search_documents(doctype="Item", search_term="chawal")
Result: [{"name": "RICE-001", "item_name": "Basmati Chawal (Rice)"}]

Step 3 -> create_document(doctype="Purchase Order", data={
  "supplier": "Mohan Rice Mills",
  "items": [{"item_code": "RICE-001", "qty": 50, "uom": "Kg"}]
})
Response: "Purchase Order PO-2024-00456 ban gaya Mohan Rice Mills ke liye, 50 Kg Basmati Chawal."

---

### Example 4: Sales summary for a period (English/Hindi mix)
User: "Aaj ki sale kitni hui?"

Step 1 -> get_sales_summary(period="today")
Result: {"invoice_count": 12, "total_sales": 87500.0, "currency": "INR", "top_items": [...]}

Response: "Aaj 87,500 ki sale hui, kul 12 invoices. Top item: [item_name]."

---

### Example 5: Account balance check
User: "What is the balance in cash account?"

Step 1 -> search_documents(doctype="Account", search_term="Cash")
Result: [{"name": "Cash - WL", "account_name": "Cash"}]

Step 2 -> get_account_balance(account="Cash - WL")
Result: {"balance": 125000.0, "currency": "INR", "as_of_date": "2024-03-05"}

Response: "The Cash account balance is 1,25,000 as of today."

---

### Example 6: Stock check before order
User: "Do we have enough Saree in stock before creating order?"

Step 1 -> search_documents(doctype="Item", search_term="Saree")
Result: [{"name": "ITEM-SAREE-001", "item_name": "Banarasi Saree"}]

Step 2 -> get_stock_balance(item_code="ITEM-SAREE-001")
Result: {"data": [{"warehouse": "Main Store", "actual_qty": 150}], "total_value": 75000.0}

Response: "Yes, 150 units of Banarasi Saree available in Main Store (value 75,000). Shall I proceed with the order?"

---

### Example 7: Multi-entity disambiguation
User: "Show ledger for Raju"

Step 1 -> search_documents(doctype="Customer", search_term="Raju")
Result: [{"name": "Raju Textiles"}, {"name": "Raju & Sons"}]

Response: "Found multiple parties named Raju. Which one did you mean?
1. Raju Textiles (Customer)
2. Raju & Sons (Customer)
Please specify."

---

## Key Rules for Multi-Step Actions

1. Always resolve entities first before creating or querying documents.
2. Disambiguate when multiple matches exist - ask the user to clarify.
3. Chain results - use names/IDs from Step N as inputs to Step N+1.
4. Confirm before creation - for new documents, briefly confirm key details.
5. Use defaults - company, posting_date, etc. are auto-filled; do not ask unless needed.
6. Hinglish support - respond in the same language mix the user used.
"""

FINANCIAL_CONTEXT_PROMPT = """
## Financial Query Guidelines

- Use get_account_balance for account-specific balance queries.
- Use get_party_outstanding for customer/supplier receivables and payables.
- Use get_general_ledger for detailed transaction history.
- Use get_sales_summary for period-based sales analytics.
- Use get_stock_balance for inventory queries.
- Always include currency in financial responses.
- Format large numbers with commas (e.g., 1,25,000 not 125000).
- When dates are ambiguous, default to current date.
"""

ENTITY_RESOLUTION_PROMPT = """
## Entity Resolution Guidelines

Before creating or querying any document involving a party (Customer, Supplier, Employee)
or item, always search first to get the exact system name.

- User says "Ram" -> search Customer for "Ram" -> get exact name "Ram Traders Pvt Ltd"
- User says "chawal" -> search Item for "chawal" -> get item_code "RICE-BASMATI-001"
- If no match found, ask user to confirm or provide more details.
- If multiple matches, show options and ask user to choose.
- Never guess or assume a party/item name without searching first.
"""
