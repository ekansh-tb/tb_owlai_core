from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
import frappe
from frappe.utils import today, add_days, get_first_day, get_last_day, getdate
from tb_owlai_core.plugins.base import BaseTool


class GetSalesSummarySchema(BaseModel):
    period: str = Field(..., description="Period for summary: 'today', 'yesterday', 'this_week', 'this_month', 'last_month'")
    company: Optional[str] = Field(None, description="Company name. Defaults to user's default company.")


class GetSalesSummary(BaseTool):
    def __init__(self):
        super().__init__()
        self.name = "get_sales_summary"
        self.description = "Get a summary of sales invoices for a given period including totals, outstanding amounts, and top items."
        self.category = "Financial Intelligence"
        self.args_schema = GetSalesSummarySchema

    def _get_date_range(self, period: str):
        today_date = getdate(today())

        if period == "today":
            return str(today_date), str(today_date)
        elif period == "yesterday":
            yesterday = add_days(today_date, -1)
            return str(yesterday), str(yesterday)
        elif period == "this_week":
            # Week starts on Monday
            day_of_week = today_date.weekday()
            week_start = add_days(today_date, -day_of_week)
            return str(week_start), str(today_date)
        elif period == "this_month":
            month_start = get_first_day(today_date)
            return str(month_start), str(today_date)
        elif period == "last_month":
            last_month_end = add_days(get_first_day(today_date), -1)
            last_month_start = get_first_day(last_month_end)
            return str(last_month_start), str(last_month_end)
        else:
            return str(today_date), str(today_date)

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if not frappe.has_permission("Sales Invoice", "read"):
            return {"error": "Permission denied for Sales Invoice"}

        period = arguments.get("period", "today")
        company = arguments.get("company") or frappe.defaults.get_user_default("Company")

        valid_periods = ["today", "yesterday", "this_week", "this_month", "last_month"]
        if period not in valid_periods:
            return {"error": f"Invalid period '{period}'. Must be one of: {', '.join(valid_periods)}"}

        from_date, to_date = self._get_date_range(period)

        params = {"from_date": from_date, "to_date": to_date}
        company_condition = ""
        if company:
            company_condition = "AND company = %(company)s"
            params["company"] = company

        summary_result = frappe.db.sql("""
            SELECT
                COUNT(*) as invoice_count,
                SUM(grand_total) as total_sales,
                SUM(outstanding_amount) as outstanding
            FROM `tabSales Invoice`
            WHERE docstatus = 1
            AND posting_date BETWEEN %(from_date)s AND %(to_date)s
            {company_condition}
        """.format(company_condition=company_condition),
            params, as_dict=True)

        summary = summary_result[0] if summary_result else {}
        invoice_count = int(summary.get("invoice_count") or 0)
        total_sales = float(summary.get("total_sales") or 0.0)
        outstanding = float(summary.get("outstanding") or 0.0)

        top_items_result = frappe.db.sql("""
            SELECT
                sii.item_name,
                SUM(sii.qty) as qty,
                SUM(sii.amount) as amount
            FROM `tabSales Invoice Item` sii
            INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
            WHERE si.docstatus = 1
            AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
            {company_condition}
            GROUP BY sii.item_name
            ORDER BY amount DESC
            LIMIT 5
        """.format(company_condition=company_condition.replace("company", "si.company")),
            params, as_dict=True)

        currency = None
        if company:
            company_doc = frappe.get_cached_doc("Company", company)
            currency = company_doc.default_currency

        return {
            "period": period,
            "from_date": from_date,
            "to_date": to_date,
            "invoice_count": invoice_count,
            "total_sales": total_sales,
            "outstanding": outstanding,
            "currency": currency,
            "top_items": top_items_result,
            "company": company,
        }
