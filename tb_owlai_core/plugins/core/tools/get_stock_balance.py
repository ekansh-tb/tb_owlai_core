from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
import frappe
from tb_owlai_core.plugins.base import BaseTool


class GetStockBalanceSchema(BaseModel):
    item_code: Optional[str] = Field(None, description="Filter by item code")
    warehouse: Optional[str] = Field(None, description="Filter by warehouse name")
    company: Optional[str] = Field(None, description="Company name. Defaults to user's default company.")


class GetStockBalance(BaseTool):
    def __init__(self):
        super().__init__()
        self.name = "get_stock_balance"
        self.description = "Get current stock balance from the Bin (inventory) for items and warehouses."
        self.category = "Financial Intelligence"
        self.args_schema = GetStockBalanceSchema

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        has_bin_perm = frappe.has_permission("Bin", "read")
        has_sle_perm = frappe.has_permission("Stock Ledger Entry", "read")

        if not has_bin_perm and not has_sle_perm:
            return {"error": "Permission denied for Bin and Stock Ledger Entry"}

        item_code = arguments.get("item_code")
        warehouse = arguments.get("warehouse")
        company = arguments.get("company") or frappe.defaults.get_user_default("Company")

        conditions = ["b.actual_qty != 0"]
        params = {}

        if item_code:
            conditions.append("b.item_code = %(item_code)s")
            params["item_code"] = item_code

        if warehouse:
            conditions.append("b.warehouse = %(warehouse)s")
            params["warehouse"] = warehouse

        if company:
            conditions.append("w.company = %(company)s")
            params["company"] = company

        where_clause = " AND ".join(conditions)

        # Join with Warehouse to filter by company if needed
        join_clause = ""
        if company:
            join_clause = "INNER JOIN `tabWarehouse` w ON w.name = b.warehouse"

        result = frappe.db.sql("""
            SELECT
                b.item_code,
                b.warehouse,
                b.actual_qty,
                b.valuation_rate,
                b.stock_value
            FROM `tabBin` b
            {join_clause}
            WHERE {where_clause}
            ORDER BY b.stock_value DESC
        """.format(join_clause=join_clause, where_clause=where_clause),
            params, as_dict=True)

        total_value = sum(float(row.get("stock_value") or 0) for row in result)

        return {
            "data": result,
            "count": len(result),
            "total_value": total_value,
            "filters": {
                "item_code": item_code,
                "warehouse": warehouse,
                "company": company,
            },
        }
