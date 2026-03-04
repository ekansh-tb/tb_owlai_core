from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
import frappe
from tb_owlai_core.plugins.base import BaseTool


class GetPartyOutstandingSchema(BaseModel):
    party: str = Field(..., description="Party name (Customer or Supplier)")
    party_type: Optional[str] = Field(None, description="Party type: 'Customer' or 'Supplier'. Auto-detected if not provided.")
    company: Optional[str] = Field(None, description="Company name. Defaults to user's default company.")


class GetPartyOutstanding(BaseTool):
    def __init__(self):
        super().__init__()
        self.name = "get_party_outstanding"
        self.description = "Get the outstanding balance for a customer or supplier party."
        self.category = "Financial Intelligence"
        self.args_schema = GetPartyOutstandingSchema

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if not frappe.has_permission("GL Entry", "read"):
            return {"error": "Permission denied for GL Entry"}

        party = arguments.get("party")
        party_type = arguments.get("party_type")
        company = arguments.get("company") or frappe.defaults.get_user_default("Company")

        # Auto-detect party_type if not provided
        if not party_type:
            if frappe.db.exists("Customer", party):
                party_type = "Customer"
            elif frappe.db.exists("Supplier", party):
                party_type = "Supplier"
            else:
                return {"error": f"Party '{party}' not found as Customer or Supplier"}

        params = {"party": party, "party_type": party_type}

        company_condition = ""
        if company:
            company_condition = "AND company = %(company)s"
            params["company"] = company

        result = frappe.db.sql("""
            SELECT SUM(debit - credit) as outstanding
            FROM `tabGL Entry`
            WHERE party = %(party)s
            AND party_type = %(party_type)s
            AND is_cancelled = 0
            {company_condition}
        """.format(company_condition=company_condition),
            params, as_dict=True)

        outstanding = result[0].get("outstanding") if result else 0
        outstanding = float(outstanding) if outstanding is not None else 0.0

        currency = None
        if company:
            company_doc = frappe.get_cached_doc("Company", company)
            currency = company_doc.default_currency

        return {
            "party": party,
            "party_type": party_type,
            "outstanding": outstanding,
            "currency": currency,
            "company": company,
            "note": "Positive value means party owes us; negative means we owe them" if party_type == "Customer"
                    else "Negative value means we owe them; positive means they owe us",
        }
