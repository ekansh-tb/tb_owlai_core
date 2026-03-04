"""
Dynamic Tool Factory — Auto-generates tools from Frappe DocType metadata.

Instead of maintaining 14 static tools, this factory generates context-aware
tools for every important DocType in the bench. A "Sales Invoice" bench gets
list_sales_invoices, create_sales_invoice, etc. — tools the LLM can call
directly without needing to know the doctype parameter.

The factory reads the bench_map from Redis (built by bench_introspector)
and generates lightweight tool wrappers around the core CRUD operations.
"""

import frappe
import json

from tb_owlai_core.intelligence.bench_introspector import get_bench_map, get_alias_map

logger = frappe.logger("owlai.tool_factory")

# Redis cache for generated tools
CACHE_KEY_DYNAMIC_TOOLS = "owlai:dynamic_tools"
CACHE_TTL = 3600  # 1 hour — refreshed on migrate


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def generate_dynamic_tools():
    """Generate dynamic tools from bench metadata.

    Returns dict of {tool_name: tool_config} where tool_config has
    name, description, category, inputSchema, execute (callable).
    Cached in Redis for 1 hour to avoid regenerating on every request.
    """
    # Check Redis cache first
    try:
        cached = frappe.cache.get_value(CACHE_KEY_DYNAMIC_TOOLS)
        if cached:
            return json.loads(cached) if isinstance(cached, str) else cached
    except Exception:
        pass

    bench_map = get_bench_map()
    if not bench_map:
        logger.warning("No bench_map available — skipping dynamic tool generation")
        return {}

    tools = {}
    categories = bench_map.get("domain_categories", {})

    # Generate tools for important DocType categories
    important_dts = set()

    # People (Employee, Customer, Supplier, etc.)
    for dt in categories.get("people", [])[:15]:
        important_dts.add(dt)

    # Transactions (Sales Invoice, Purchase Order, etc.)
    for dt in categories.get("transactions", [])[:20]:
        important_dts.add(dt)

    # Masters (Item, Warehouse, Company, etc.)
    for dt in categories.get("masters", [])[:15]:
        important_dts.add(dt)

    # Trees (Department, Cost Center, Account, etc.)
    for dt in categories.get("trees", [])[:10]:
        important_dts.add(dt)

    for dt_name in important_dts:
        dt_tools = _generate_tools_for_doctype(dt_name, bench_map)
        tools.update(dt_tools)

    # Cache in Redis
    try:
        frappe.cache.set_value(
            CACHE_KEY_DYNAMIC_TOOLS,
            json.dumps(tools, default=str),
            expires_in_sec=CACHE_TTL
        )
    except Exception:
        pass

    logger.info(f"Generated {len(tools)} dynamic tools for {len(important_dts)} DocTypes")
    return tools


def invalidate_cache():
    """Clear the dynamic tools cache. Called on after_migrate."""
    try:
        frappe.cache.delete_value(CACHE_KEY_DYNAMIC_TOOLS)
    except Exception:
        pass


def get_relevant_dynamic_tools(user_message, max_tools=4):
    """Select the most relevant dynamic tools for a user message.

    Uses DocType detection from the message to find matching tools.
    Returns list of tool configs (not schemas) for the detected DocTypes.
    Prioritizes the first detected DocType (most relevant).
    """
    from tb_owlai_core.intelligence.bench_introspector import detect_doctypes_in_text

    detected_dts = detect_doctypes_in_text(user_message)
    if not detected_dts:
        return []

    # Load all dynamic tools (cached)
    all_dynamic = generate_dynamic_tools()
    if not all_dynamic:
        return []

    # Find tools matching detected DocTypes — exact doctype match, not slug substring
    matched = []
    for dt_name in detected_dts:
        for tool_name, tool_config in all_dynamic.items():
            if tool_config.get("doctype") == dt_name:
                matched.append(tool_config)
        # Stop after filling max_tools to prioritize the first (most relevant) DocType
        if len(matched) >= max_tools:
            break

    # Deduplicate and limit
    seen = set()
    unique = []
    for t in matched:
        if t["name"] not in seen:
            seen.add(t["name"])
            unique.append(t)

    return unique[:max_tools]


# ------------------------------------------------------------------
# Tool Generation per DocType
# ------------------------------------------------------------------

def _generate_tools_for_doctype(dt_name, bench_map):
    """Generate a set of tools for a single DocType."""
    tools = {}
    slug = _to_slug(dt_name)
    module = _get_module_for_dt(dt_name, bench_map)

    # 1. List tool (always)
    list_name = f"list_{slug}s" if not slug.endswith("s") else f"list_{slug}"
    tools[list_name] = {
        "name": list_name,
        "description": f"List {dt_name} records. Use limit_page_length=0 for count only.",
        "category": module,
        "doctype": dt_name,
        "operation": "list",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filters": {
                    "type": "object",
                    "description": f"Filter {dt_name} records. Example: {{\"status\": \"Active\"}}"
                },
                "fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Fields to return. Default: name + key fields."
                },
                "limit_page_length": {
                    "type": "integer",
                    "description": "Number of records. Use 0 for count only. Default: 20."
                },
                "order_by": {
                    "type": "string",
                    "description": "Sort order. Example: 'creation desc'"
                }
            }
        }
    }

    # 2. Get tool (always)
    tools[f"get_{slug}"] = {
        "name": f"get_{slug}",
        "description": f"Get a specific {dt_name} by name.",
        "category": module,
        "doctype": dt_name,
        "operation": "get",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": f"The {dt_name} document name/ID."
                }
            },
            "required": ["name"]
        }
    }

    # 3. Create tool (for non-single, non-tree DocTypes)
    if dt_name not in bench_map.get("single_doctypes", []):
        tools[f"create_{slug}"] = {
            "name": f"create_{slug}",
            "description": f"Create a new {dt_name}.",
            "category": module,
            "doctype": dt_name,
            "operation": "create",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "data": {
                        "type": "object",
                        "description": f"Field values for the new {dt_name}."
                    }
                },
                "required": ["data"]
            }
        }

    # 4. Submit/Cancel for submittable DocTypes
    if dt_name in bench_map.get("submittable_doctypes", []):
        tools[f"submit_{slug}"] = {
            "name": f"submit_{slug}",
            "description": f"Submit a {dt_name} document.",
            "category": module,
            "doctype": dt_name,
            "operation": "submit",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": f"The {dt_name} document name to submit."
                    }
                },
                "required": ["name"]
            }
        }

    return tools


# ------------------------------------------------------------------
# Dynamic Tool Executor
# ------------------------------------------------------------------

def execute_dynamic_tool(tool_config, arguments):
    """Execute a dynamically generated tool.

    Routes to the appropriate frappe API based on the operation type.
    """
    dt_name = tool_config["doctype"]
    operation = tool_config["operation"]

    try:
        if operation == "list":
            return _exec_list(dt_name, arguments)
        elif operation == "get":
            return _exec_get(dt_name, arguments)
        elif operation == "create":
            return _exec_create(dt_name, arguments)
        elif operation == "submit":
            return _exec_submit(dt_name, arguments)
        else:
            return {"error": f"Unknown operation: {operation}"}
    except Exception as e:
        return {"error": str(e)}


def _exec_list(dt_name, args):
    """List documents with filters."""
    if not frappe.has_permission(dt_name, "read"):
        return {"error": f"No permission to read {dt_name}"}

    filters = args.get("filters", {})
    fields = args.get("fields", ["name"])
    limit = args.get("limit_page_length", 20)
    order_by = args.get("order_by", "creation desc")

    # If limit is 0, return count
    if limit == 0:
        count = frappe.db.count(dt_name, filters=filters)
        return {"doctype": dt_name, "count": count}

    # Add key display fields if only "name" requested
    if fields == ["name"]:
        fields = _get_display_fields(dt_name)

    results = frappe.get_list(
        dt_name,
        filters=filters,
        fields=fields,
        limit_page_length=limit,
        order_by=order_by,
    )

    return {
        "doctype": dt_name,
        "data": results,
        "count": len(results),
        "total": frappe.db.count(dt_name, filters=filters),
    }


def _exec_get(dt_name, args):
    """Get a single document."""
    name = args.get("name")
    if not name:
        return {"error": "Document name is required"}

    if not frappe.has_permission(dt_name, "read", doc=name):
        return {"error": f"No permission to read {dt_name} {name}"}

    doc = frappe.get_doc(dt_name, name)
    return {"doctype": dt_name, "data": doc.as_dict()}


def _exec_create(dt_name, args):
    """Create a new document."""
    if not frappe.has_permission(dt_name, "create"):
        return {"error": f"No permission to create {dt_name}"}

    data = args.get("data", {})
    doc = frappe.new_doc(dt_name)
    doc.update(data)
    doc.insert()
    frappe.db.commit()

    return {"doctype": dt_name, "name": doc.name, "status": "created"}


def _exec_submit(dt_name, args):
    """Submit a document."""
    name = args.get("name")
    if not name:
        return {"error": "Document name is required"}

    if not frappe.has_permission(dt_name, "submit", doc=name):
        return {"error": f"No permission to submit {dt_name} {name}"}

    doc = frappe.get_doc(dt_name, name)
    doc.submit()
    frappe.db.commit()

    return {"doctype": dt_name, "name": doc.name, "status": "submitted"}


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _to_slug(dt_name):
    """Convert DocType name to a tool-friendly slug.
    'Sales Invoice' -> 'sales_invoice'
    """
    return dt_name.lower().replace(" ", "_").replace("-", "_")


def _get_module_for_dt(dt_name, bench_map):
    """Find the module a DocType belongs to."""
    for mod, info in bench_map.get("modules", {}).items():
        if dt_name in info.get("doctypes", []):
            return mod
    return "Other"


def _get_display_fields(dt_name):
    """Get key display fields for a DocType (name + title/subject + status)."""
    fields = ["name"]
    try:
        meta = frappe.get_meta(dt_name)
        # Add title field
        if meta.title_field and meta.title_field != "name":
            fields.append(meta.title_field)

        # Add common display fields
        for fname in ["status", "docstatus", "owner", "creation", "modified"]:
            if meta.has_field(fname):
                fields.append(fname)

        # Add first few important fields (Link, Select, Data — not text/code)
        for df in meta.fields[:20]:
            if (df.fieldtype in ("Link", "Select", "Data", "Date", "Currency", "Int", "Float")
                    and not df.hidden
                    and df.fieldname not in fields
                    and len(fields) < 8):
                fields.append(df.fieldname)

    except Exception:
        pass

    return fields
