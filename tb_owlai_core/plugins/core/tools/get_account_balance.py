from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
import frappe
from tb_owlai_core.plugins.base import BaseTool


class GetAccountBalanceSchema(BaseModel):
    account: str = Field(..., description="Account name or code to get balance for")
    date: Optional[str] = Field(None, description="Date to get balance as of (YYYY-MM-DD). Defaults to today.")
    company: Optional[str] = Field(None, description="Company name. Defaults to user's default company.")


class GetAccountBalance(BaseTool):
    def __init__(self):
        super().__init__()
        self.name = "get_account_balance"
        self.description = "Get the current balance of a specific GL account as of a given date."
        self.category = "Financial Intelligence"
        self.args_schema = GetAccountBalanceSchema

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if not frappe.has_permission("GL Entry", "read"):
            return {"error": "Permission denied for GL Entry"}

        account = arguments.get("account")
        date = arguments.get("date")
        company = arguments.get("company") or frappe.defaults.get_user_default("Company")

        params = {"account": account}

        date_condition = ""
        if date:
            date_condition = "AND posting_date <= %(date)s"
            params["date"] = date

        company_condition = ""
        if company:
            company_condition = "AND company = %(company)s"
            params["company"] = company

        result = frappe.db.sql("""
            SELECT SUM(debit - credit) as balance
            FROM `tabGL Entry`
            WHERE account = %(account)s
            AND is_cancelled = 0
            {date_condition}
            {company_condition}
        """.format(date_condition=date_condition, company_condition=company_condition),
            params, as_dict=True)

        balance = result[0].get("balance") if result else 0
        balance = float(balance) if balance is not None else 0.0

        currency = None
        if company:
            company_doc = frappe.get_cached_doc("Company", company)
            currency = company_doc.default_currency

        return {
            "account": account,
            "balance": balance,
            "currency": currency,
            "as_of_date": date or frappe.utils.today(),
            "company": company,
        }
