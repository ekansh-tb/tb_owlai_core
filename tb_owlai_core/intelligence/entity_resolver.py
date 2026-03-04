"""
Entity Resolver - Cross-DocType entity search with scoring and Redis caching.
"""
import re
import json
import frappe


# Keywords to strip before entity candidate extraction
_STOP_WORDS = {
    "balance", "show", "open", "get", "find", "list", "total", "outstanding",
    "create", "make", "new", "add", "update", "edit", "delete", "remove",
    "invoice", "order", "payment", "report", "statement", "ledger",
    "for", "of", "the", "a", "an", "in", "on", "at", "by", "with",
    "and", "or", "is", "are", "was", "what", "how", "much", "many",
}

# DocTypes to search in priority order, with their display name fields
_SEARCH_DOCTYPES = [
    ("Customer", ["customer_name"]),
    ("Supplier", ["supplier_name"]),
    ("Employee", ["employee_name", "first_name", "last_name"]),
    ("Item", ["item_name"]),
    ("Lead", ["lead_name", "first_name"]),
]

_CACHE_TTL = 300  # 5 minutes


def _cache_key(text: str) -> str:
    safe = re.sub(r"[^a-z0-9_]", "_", text.lower().strip())
    return f"owlai:entity_resolver:{safe}"


def _extract_candidates(text: str) -> list:
    """Extract candidate entity names from input text by removing stop words."""
    tokens = re.split(r"[\s,;:.!?]+", text.strip())
    candidates = []

    single = [t for t in tokens if t.lower() not in _STOP_WORDS and len(t) >= 2]
    candidates.extend(single)

    for i in range(len(tokens) - 1):
        a, b = tokens[i], tokens[i + 1]
        if a.lower() not in _STOP_WORDS or b.lower() not in _STOP_WORDS:
            bigram = f"{a} {b}"
            if len(bigram) >= 3:
                candidates.append(bigram)

    for i in range(len(tokens) - 2):
        a, b, c = tokens[i], tokens[i + 1], tokens[i + 2]
        trigram = f"{a} {b} {c}"
        if len(trigram) >= 5:
            candidates.append(trigram)

    seen = set()
    unique = []
    for c in candidates:
        key = c.lower()
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique


def _score_match(candidate: str, record_name: str, display_value: str) -> float:
    """Score a match between a candidate string and a record."""
    c = candidate.lower().strip()
    name = (record_name or "").lower().strip()
    display = (display_value or "").lower().strip()

    for val in (name, display):
        if not val:
            continue
        if c == val:
            return 1.0
        if val.startswith(c) or c.startswith(val):
            return 0.7
        if c in val or val in c:
            return 0.5

    return 0.0


def _sanitize(text: str) -> str:
    """Remove characters that could cause SQL injection in LIKE queries."""
    return re.sub(r"[%_\\'\";]", "", text)


def _search_doctype(doctype: str, display_fields: list, candidate: str) -> list:
    """Search a DocType for a candidate string, return scored matches."""
    if not frappe.has_permission(doctype, "read"):
        return []

    safe_candidate = _sanitize(candidate)
    if not safe_candidate:
        return []

    matches = []

    try:
        records = frappe.db.sql("""
            SELECT name FROM `tab{doctype}`
            WHERE name LIKE %(pattern)s
            LIMIT 5
        """.format(doctype=doctype),
            {"pattern": f"%{safe_candidate}%"}, as_dict=True)

        for rec in records:
            score = _score_match(candidate, rec["name"], rec["name"])
            if score > 0:
                matches.append({
                    "doctype": doctype,
                    "name": rec["name"],
                    "display": rec["name"],
                    "confidence": score,
                    "matched_on": "name",
                })

        for field in display_fields:
            try:
                rows = frappe.db.sql("""
                    SELECT name, `{field}` as display_val FROM `tab{doctype}`
                    WHERE `{field}` LIKE %(pattern)s
                    LIMIT 5
                """.format(doctype=doctype, field=field),
                    {"pattern": f"%{safe_candidate}%"}, as_dict=True)

                for row in rows:
                    score = _score_match(candidate, row["name"], row.get("display_val", ""))
                    if score > 0:
                        matches.append({
                            "doctype": doctype,
                            "name": row["name"],
                            "display": row.get("display_val") or row["name"],
                            "confidence": score,
                            "matched_on": field,
                        })
            except Exception:
                pass

    except Exception:
        pass

    return matches


# Aliases for test compatibility
_calculate_score = _score_match
_sanitize_input = _sanitize


def get_entity_context_string(entity_name: str) -> str:
    """Return a human-readable context string for an entity name."""
    results = resolve_entities(entity_name)
    if not results:
        return f"No entity found for '{entity_name}'"
    top = results[0]
    return f"{top['doctype']}: {top['display']} (confidence: {top['confidence']:.0%})"


def resolve_entities(text: str) -> list:
    """
    Resolve entity names from natural language text.

    Returns a list of matches sorted by confidence (highest first):
    [{"doctype": "Customer", "name": "Ram Traders", "display": "Ram Traders", "confidence": 1.0}, ...]
    """
    if not text or not text.strip():
        return []

    cache_key = _cache_key(text)
    try:
        cached = frappe.cache().get_value(cache_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    candidates = _extract_candidates(text)
    if not candidates:
        return []

    all_matches = []
    seen_names = set()

    for doctype, display_fields in _SEARCH_DOCTYPES:
        for candidate in candidates:
            results = _search_doctype(doctype, display_fields, candidate)
            for match in results:
                dedup_key = f"{match['doctype']}:{match['name']}"
                if dedup_key not in seen_names:
                    seen_names.add(dedup_key)
                    all_matches.append(match)
                else:
                    for existing in all_matches:
                        if f"{existing['doctype']}:{existing['name']}" == dedup_key:
                            if match["confidence"] > existing["confidence"]:
                                existing["confidence"] = match["confidence"]
                            break

    all_matches.sort(key=lambda x: x["confidence"], reverse=True)

    try:
        frappe.cache().set_value(cache_key, json.dumps(all_matches), expires_in_sec=_CACHE_TTL)
    except Exception:
        pass

    return all_matches
