import frappe
import json

class OwlContext:
    def __init__(self, route=None, doctype=None, docname=None, form_data=None, selected_items=None):
        self.route = route
        self.form_data = form_data or {}
        self.selected_items = selected_items or []
        self.doctype = doctype
        self.docname = docname
        self._bench_map = None

        if not self.doctype or not self.docname:
            self._parse_route(route)

    def get(self, key, default=None):
        return getattr(self, key, default)

    def _parse_route(self, route):
        """
        Extracts DocType and DocName from the current route.
        Supported formats:
        - Form/ToDo/Task-001
        - List/ToDo/List
        - app/todo (URL style)
        """
        if not route: return
        
        parts = route.strip("/").split("/")
        
        # Handle /app/ prefix if present
        if parts[0] == "app":
            parts.pop(0)
            
        if not parts: return

        # Case 1: Standard Desk Route (Form/DocType/Name or List/DocType/...)
        if parts[0] in ["Form", "List"]:
            if len(parts) >= 2:
                self.doctype = parts[1]
                if parts[0] == "Form" and len(parts) >= 3:
                     self.docname = parts[2]
            return

        # Case 2: URL slug style (todo, user, etc.)
        doctype_slug = parts[0]
        if doctype_slug in ["query-report", "dashboard-view", "kanban-view"]:
             return 
             
        # Try to find DocType
        # 1. Direct Name Match
        if frappe.db.exists("DocType", doctype_slug):
            self.doctype = doctype_slug
        else:
            # 2. Slug to Title
            possible_name = doctype_slug.replace("-", " ").title()
            if frappe.db.exists("DocType", possible_name):
                 self.doctype = possible_name
            else:
                # 3. DB Search
                try:
                     dt = frappe.db.get_value("DocType", {"name": ["like", doctype_slug]}, "name")
                     if dt: self.doctype = dt
                except Exception:
                    pass
        
        # Extract DocName if available (doctype/docname)
        if self.doctype and len(parts) >= 2:
            self.docname = parts[1]

    def get_schema_context_string(self):
        """
        Returns a formatted string containing the schema of the current DocType.
        """
        if not self.doctype:
            return ""
            
        try:
            meta = frappe.get_meta(self.doctype)
            # Basic Info
            schema_text = f"DocType: {self.doctype}\n"
            schema_text += f"Description: {meta.description or 'No description'}\n"
            schema_text += f"Is Submittable: {'Yes' if meta.is_submittable else 'No'}\n"
            
            # Fields
            schema_text += "Fields (First 50):\n"
            fields = []
            for df in meta.fields:
                 if df.fieldtype not in ["Section Break", "Column Break", "Tab Break", "HTML", "Image", "Fold"] and not df.hidden:
                     field_info = f"- {df.fieldname} ({df.fieldtype}): {df.label}"
                     if df.options and df.fieldtype in ["Link", "Select"]:
                          field_info += f" [Options: {df.options}]"
                     if df.reqd:
                          field_info += " [Required]"
                     fields.append(field_info)
            
            schema_text += "\n".join(fields[:50])
            
            return f"""
\n---
CONTEXT: USER IS CURRENTLY VIEWING DOCTYPE '{self.doctype}'.
SCHEMA INFORMATION:
{schema_text}
---
"""
        except Exception as e:
            # Don't fail the whole request if schema fetch fails
            frappe.log_error(f"Schema fetch error for {self.doctype}: {e}")
            return ""

    def get_data_context_string(self):
        """
        Returns a formatted string containing current form data or selection.
        """
        context_str = ""
        
        if self.form_data:
            context_str += f"\n--- CURRENT FORM DATA ({self.doctype}) ---\n"
            # Truncate values to prevent prompt injection from large form fields
            safe_data = {}
            for k, v in self.form_data.items() if isinstance(self.form_data, dict) else []:
                str_v = str(v) if v is not None else ""
                safe_data[k] = str_v[:500] if len(str_v) > 500 else str_v
            context_str += json.dumps(safe_data, indent=2, default=str)
            context_str += "\n-------------------------------------\n"
            
        if self.selected_items:
            context_str += f"\n--- SELECTED ITEMS ({len(self.selected_items)}) ---\n"
            context_str += json.dumps(self.selected_items, indent=2)
            context_str += "\n-------------------------------------\n"
            
        return context_str

    def get_full_context_string(self):
        """
        Combines Route, Schema, and Data context.
        """
        full_context = f"Current Route: {self.route}\n"
        if self.docname:
            full_context += f"Current Document: {self.docname}\n"

        full_context += self.get_schema_context_string()
        full_context += self.get_data_context_string()
        return full_context

    # ------------------------------------------------------------------
    # v2 Context Layers (used by OwlEngine._build_system_prompt)
    # ------------------------------------------------------------------

    def get_domain_context(self):
        """Layer 1: Business domain context from bench introspection.
        Cached in Redis, ~0ms to retrieve.
        """
        try:
            from tb_owlai_core.intelligence.bench_introspector import get_bench_map
            bench_map = get_bench_map()
            if not bench_map:
                return ""

            domain = bench_map.get("business_domain", "General Business")
            apps = bench_map.get("installed_apps", [])
            # Filter out framework apps for cleaner context
            business_apps = [a for a in apps if a not in ("frappe",)]

            modules = bench_map.get("modules", {})
            # Top modules by DocType count
            top_modules = sorted(
                [(mod, len(info.get("doctypes", []))) for mod, info in modules.items()],
                key=lambda x: x[1], reverse=True
            )[:8]

            categories = bench_map.get("domain_categories", {})
            people = categories.get("people", [])[:5]
            transactions = categories.get("transactions", [])[:8]
            masters = categories.get("masters", [])[:5]

            lines = [f"\nBUSINESS DOMAIN: {domain}"]
            lines.append(f"Apps: {', '.join(business_apps)}")
            if top_modules:
                lines.append(f"Key modules: {', '.join(f'{m}({c})' for m, c in top_modules)}")
            if people:
                lines.append(f"People: {', '.join(people)}")
            if transactions:
                lines.append(f"Transactions: {', '.join(transactions)}")
            if masters:
                lines.append(f"Masters: {', '.join(masters)}")

            return "\n".join(lines)
        except Exception:
            return ""

    def get_user_context(self):
        """Layer 2: Current user's role and defaults context."""
        try:
            user = frappe.session.user
            user_doc = frappe.get_doc("User", user)
            full_name = user_doc.full_name or user
            roles = [r.role for r in user_doc.roles if r.role not in ("All", "Guest")][:8]
            company = frappe.defaults.get_user_default("Company") or ""

            lines = [f"\nUSER: {full_name}"]
            if company:
                lines.append(f"Company: {company}")
            if roles:
                lines.append(f"Roles: {', '.join(roles)}")

            # User defaults
            defaults = {}
            for key in ("warehouse", "cost_center", "department"):
                val = frappe.defaults.get_user_default(key)
                if val:
                    defaults[key] = val
            if defaults:
                lines.append(f"Defaults: {', '.join(f'{k}={v}' for k, v in defaults.items())}")

            return "\n".join(lines)
        except Exception:
            return ""

    def get_knowledge_context(self, query):
        """Layer 4: Knowledge base context from RAG search."""
        try:
            from tb_owlai_core.intelligence.rag_engine import search
            results = search(query, limit=3)
            if not results:
                return ""

            lines = ["\nKNOWLEDGE BASE:"]
            for r in results:
                if r.get("score", 0) < 0.3:
                    continue
                content = r.get("content", "")[:300]
                title = r.get("meta", {}).get("title", "")
                lines.append(f"- [{title}] {content}")

            return "\n".join(lines) if len(lines) > 1 else ""
        except Exception:
            return ""

    def get_entity_context(self, user_message):
        """Layer 5: Entity context from entity resolver.

        Runs the entity resolver on the user message and returns
        a formatted string of resolved entities (customers, suppliers, etc.).
        """
        try:
            from tb_owlai_core.intelligence.entity_resolver import resolve_entities
            entities = resolve_entities(user_message)
            if not entities:
                return ""

            lines = ["\nRESOLVED ENTITIES:"]
            for entity in entities:
                doctype = entity.get("doctype", "")
                name = entity.get("name", "")
                display = entity.get("display_name") or name
                original = entity.get("original_text", "")
                if doctype and name:
                    lines.append(f"- '{original}' -> {doctype}: {display} ({name})")

            return "\n".join(lines) if len(lines) > 1 else ""
        except Exception:
            return ""

    def get_user_defaults_context(self):
        """Expose all relevant user defaults as a context string."""
        try:
            default_keys = [
                "Company", "Currency", "Warehouse", "Cost Center",
                "Department", "Territory", "Price List", "Letter Head",
            ]
            defaults = {}
            for key in default_keys:
                val = frappe.defaults.get_user_default(key)
                if val:
                    defaults[key] = val

            if not defaults:
                return ""

            lines = ["\nUSER DEFAULTS:"]
            for k, v in defaults.items():
                lines.append(f"- {k}: {v}")
            return "\n".join(lines)
        except Exception:
            return ""

    def get_recent_activity_context(self):
        """Get last 5 OwlAI Messages for conversation continuity."""
        try:
            messages = frappe.get_all(
                "OwlAI Message",
                filters={"owner": frappe.session.user},
                fields=["role", "content", "creation"],
                order_by="creation desc",
                limit_page_length=5,
            )
            if not messages:
                return ""

            lines = ["\nRECENT ACTIVITY:"]
            for msg in reversed(messages):
                role = msg.get("role", "")
                content = (msg.get("content") or "")[:150]
                lines.append(f"- [{role}] {content}")
            return "\n".join(lines)
        except Exception:
            return ""
