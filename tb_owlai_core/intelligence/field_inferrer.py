"""
Field Inferrer - Infers mandatory and common field values from context and defaults.

Inference order (never overrides user-provided values):
1. User defaults (frappe.defaults)
2. Form context (OwlContext.form_data)
3. Single-option Links (auto-fill if only 1 record exists)
4. Date defaults (today for Date fields)
5. Common patterns (company, fiscal_year, cost_center)
"""
import frappe
from frappe.utils import today, nowdate
from typing import Dict, Any, Optional


_SKIP_FIELDS = {"name", "owner", "creation", "modified", "modified_by", "docstatus", "idx", "doctype"}

_COMMON_PATTERNS = {
    "company": lambda: frappe.defaults.get_user_default("Company"),
    "fiscal_year": lambda: _get_current_fiscal_year(),
    "cost_center": lambda: _get_default_cost_center(),
    "currency": lambda: frappe.defaults.get_user_default("Currency"),
    "price_list": lambda: frappe.defaults.get_user_default("Price List") or frappe.db.get_single_value("Selling Settings", "selling_price_list"),
    "selling_price_list": lambda: frappe.defaults.get_user_default("Price List") or frappe.db.get_single_value("Selling Settings", "selling_price_list"),
    "buying_price_list": lambda: frappe.db.get_single_value("Buying Settings", "buying_price_list"),
    "territory": lambda: frappe.defaults.get_user_default("Territory"),
    "customer_group": lambda: frappe.db.get_single_value("Selling Settings", "customer_group"),
    "supplier_group": lambda: frappe.db.get_single_value("Buying Settings", "supplier_group"),
    "expense_account": lambda: _get_default_expense_account(),
    "income_account": lambda: _get_default_income_account(),
}


def _get_current_fiscal_year() -> Optional[str]:
    try:
        result = frappe.db.sql("""
            SELECT name FROM `tabFiscal Year`
            WHERE %(today)s BETWEEN year_start_date AND year_end_date
            LIMIT 1
        """, {"today": today()}, as_dict=True)
        return result[0]["name"] if result else None
    except Exception:
        return None


def _get_default_cost_center() -> Optional[str]:
    try:
        company = frappe.defaults.get_user_default("Company")
        if company:
            return frappe.db.get_value("Company", company, "cost_center")
        return None
    except Exception:
        return None


def _get_default_expense_account() -> Optional[str]:
    try:
        company = frappe.defaults.get_user_default("Company")
        if company:
            return frappe.db.get_value("Company", company, "default_expense_account")
        return None
    except Exception:
        return None


def _get_default_income_account() -> Optional[str]:
    try:
        company = frappe.defaults.get_user_default("Company")
        if company:
            return frappe.db.get_value("Company", company, "default_income_account")
        return None
    except Exception:
        return None


def _infer_from_user_defaults(fieldname: str, fieldtype: str, options: str) -> Optional[Any]:
    """Strategy 1: Check frappe user defaults."""
    try:
        val = frappe.defaults.get_user_default(fieldname)
        if val:
            return val
        val = frappe.defaults.get_user_default(fieldname.replace("_", " ").title())
        if val:
            return val
    except Exception:
        pass
    return None


def _infer_from_form_context(fieldname: str, context: Optional[Dict]) -> Optional[Any]:
    """Strategy 2: Check form context (OwlContext.form_data)."""
    if not context:
        return None
    form_data = context.get("form_data") or {}
    return form_data.get(fieldname)


def _infer_single_option_link(fieldname: str, fieldtype: str, options: str) -> Optional[Any]:
    """Strategy 3: Auto-fill Link fields that have exactly 1 record."""
    if fieldtype != "Link" or not options:
        return None
    try:
        count = frappe.db.count(options)
        if count == 1:
            return frappe.db.get_value(options, {}, "name")
    except Exception:
        pass
    return None


def _infer_date_default(fieldname: str, fieldtype: str) -> Optional[str]:
    """Strategy 4: Default Date and Datetime fields to today."""
    if fieldtype == "Date":
        return today()
    if fieldtype == "Datetime":
        return nowdate()
    return None


def _infer_common_pattern(fieldname: str) -> Optional[Any]:
    """Strategy 5: Apply common field name patterns."""
    strategy = _COMMON_PATTERNS.get(fieldname)
    if strategy:
        try:
            return strategy()
        except Exception:
            pass
    return None


# Aliases for test compatibility
def _from_date_defaults(field) -> Optional[str]:
    """Test-compatible alias: return date default for a field object."""
    return _infer_date_default(field.fieldname, field.fieldtype)


def _from_single_option(field) -> Optional[Any]:
    """Test-compatible alias: return single-option Link value for a field object."""
    return _infer_single_option_link(field.fieldname, field.fieldtype, getattr(field, "options", "") or "")


def _from_common_patterns(field, doctype: str = "") -> Optional[Any]:
    """Test-compatible alias: return common pattern value for a field object."""
    return _infer_common_pattern(field.fieldname)


def infer_fields(doctype: str, provided_data: Dict[str, Any], context: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Infer values for mandatory and common fields not already provided.

    Args:
        doctype: The DocType name.
        provided_data: Fields already provided by the user/LLM.
        context: Optional OwlContext dict with form_data, user info, etc.

    Returns:
        Dict of inferred field values (does NOT include already-provided values).
    """
    inferred = {}

    try:
        meta = frappe.get_meta(doctype)
    except Exception:
        return inferred

    for field in meta.fields:
        fname = field.fieldname
        ftype = field.fieldtype
        options = field.options or ""

        if fname in _SKIP_FIELDS:
            continue
        val = provided_data.get(fname)
        if val is not None and val != "":
            continue
        if ftype in ("Section Break", "Column Break", "HTML", "Heading", "Button", "Code", "Table", "Table MultiSelect"):
            continue

        value = _infer_from_user_defaults(fname, ftype, options)

        if value is None:
            value = _infer_from_form_context(fname, context)

        if value is None:
            value = _infer_single_option_link(fname, ftype, options)

        if value is None:
            value = _infer_date_default(fname, ftype)

        if value is None:
            value = _infer_common_pattern(fname)

        if value is not None:
            inferred[fname] = value

    return inferred


def get_missing_mandatory_fields(doctype: str, provided_data: Dict[str, Any]) -> list:
    """
    Return a list of mandatory fields that are not provided and cannot be inferred.
    Useful for prompting the user for missing required information.
    """
    try:
        meta = frappe.get_meta(doctype)
    except Exception:
        return []

    inferred = infer_fields(doctype, provided_data)
    all_available = {**inferred, **provided_data}

    missing = []
    for field in meta.fields:
        if not field.reqd:
            continue
        fname = field.fieldname
        if fname in _SKIP_FIELDS:
            continue
        val = all_available.get(fname)
        if val is None or val == "":
            missing.append({
                "fieldname": fname,
                "label": field.label or fname,
                "fieldtype": field.fieldtype,
                "options": field.options,
            })

    return missing
