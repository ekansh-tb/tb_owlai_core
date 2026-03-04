from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
import frappe
from tb_owlai_core.plugins.base import BaseTool


class GetGeneralLedgerSchema(BaseModel):
    account: Optional[str] = Field(None, description="Filter by account name")
    party: Optional[str] = Field(None, description="Filter by party name")
    from_date: Optional[str] = Field(None, description="Start date for entries (YYYY-MM-DD)")
    to_date: Optional[str] = Field(None, description="End date for entries (YYYY-MM-DD)")
    voucher_type: Optional[str] = Field(None, description="Filter by voucher type (e.g. Sales Invoice, Purchase Invoice)")
    limit: Optional[int] = Field(20, description="Maximum number of records to return. Defaults to 20.")
    company: Optional[str] = Field(None, description="Company name. Defaults to user's default company.")


class GetGeneralLedger(BaseTool):
    def __init__(self):
        super().__init__()
        self.name = "get_general_ledger"
        self.description = "Fetch general ledger entries with optional filters for account, party, date range, and voucher type."
        self.category = "Financial Intelligence"
        self.args_schema = GetGeneralLedgerSchema

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if not frappe.has_permission("GL Entry", "read"):
            return {"error": "Permission denied for GL Entry"}

        account = arguments.get("account")
        party = arguments.get("party")
        from_date = arguments.get("from_date")
        to_date = arguments.get("to_date")
        voucher_type = arguments.get("voucher_type")
        limit = arguments.get("limit") or 20
        company = arguments.get("company") or frappe.defaults.get_user_default("Company")

        conditions = ["is_cancelled = 0"]
        params = {}
        filters_applied = {}

        if account:
            conditions.append("account = %(account)s")
            params["account"] = account
            filters_applied["account"] = account

        if party:
            conditions.append("party = %(party)s")
            params["party"] = party
            filters_applied["party"] = party

        if from_date:
            conditions.append("posting_date >= %(from_date)s")
            params["from_date"] = from_date
            filters_applied["from_date"] = from_date

        if to_date:
            conditions.append("posting_date <= %(to_date)s")
            params["to_date"] = to_date
            filters_applied["to_date"] = to_date

        if voucher_type:
            conditions.append("voucher_type = %(voucher_type)s")
            params["voucher_type"] = voucher_type
            filters_applied["voucher_type"] = voucher_type

        if company:
            conditions.append("company = %(company)s")
            params["company"] = company
            filters_applied["company"] = company

        where_clause = " AND ".join(conditions)
        params["limit"] = int(limit)

        result = frappe.db.sql("""
            SELECT
                name,
                posting_date,
                account,
                party_type,
                party,
                voucher_type,
                voucher_no,
                debit,
                credit,
                remarks,
                cost_center
            FROM `tabGL Entry`
            WHERE {where_clause}
            ORDER BY posting_date DESC, creation DESC
            LIMIT %(limit)s
        """.format(where_clause=where_clause),
            params, as_dict=True)

        return {
            "data": result,
            "count": len(result),
            "filters_applied": filters_applied,
        }
