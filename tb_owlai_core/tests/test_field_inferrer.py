import frappe
from frappe.tests import IntegrationTestCase


class TestFieldInferrer(IntegrationTestCase):
    def test_empty_doctype(self):
        from tb_owlai_core.intelligence.field_inferrer import infer_fields
        result = infer_fields("", {})
        self.assertEqual(result, {})

    def test_nonexistent_doctype(self):
        from tb_owlai_core.intelligence.field_inferrer import infer_fields
        result = infer_fields("NonExistentDocType12345", {})
        self.assertEqual(result, {})

    def test_no_override_provided_values(self):
        """Field inferrer must NEVER override user-provided values."""
        from tb_owlai_core.intelligence.field_inferrer import infer_fields
        provided = {"company": "My Custom Company"}
        result = infer_fields("Sales Invoice", provided)
        # company should NOT be in result since it's already provided
        self.assertNotIn("company", result)

    def test_infer_company_default(self):
        """Should infer company from user defaults."""
        from tb_owlai_core.intelligence.field_inferrer import infer_fields
        result = infer_fields("Sales Invoice", {})
        # If user has a default company, it should be inferred
        default_company = frappe.defaults.get_user_default("Company")
        if default_company:
            self.assertEqual(result.get("company"), default_company)

    def test_date_defaults(self):
        """Date fields should default to today or today+7."""
        from tb_owlai_core.intelligence.field_inferrer import _from_date_defaults

        class MockField:
            def __init__(self, fieldname, fieldtype, reqd=True):
                self.fieldname = fieldname
                self.fieldtype = fieldtype
                self.reqd = reqd

        from frappe.utils import today
        posting = MockField("posting_date", "Date")
        result = _from_date_defaults(posting)
        self.assertEqual(result, today())

    def test_single_option_link(self):
        """If a Link target has exactly 1 record, auto-fill it."""
        from tb_owlai_core.intelligence.field_inferrer import _from_single_option

        class MockField:
            def __init__(self, options):
                self.options = options
                self.fieldtype = "Link"

        # This test depends on data, just verify it returns something or None
        mock = MockField("Company")
        result = _from_single_option(mock)
        company_count = frappe.db.count("Company")
        if company_count == 1:
            self.assertIsNotNone(result)
        # If multiple companies, should return None
        elif company_count > 1:
            self.assertIsNone(result)

    def test_currency_from_company(self):
        """Should infer currency from default company."""
        from tb_owlai_core.intelligence.field_inferrer import _from_common_patterns

        class MockField:
            def __init__(self):
                self.fieldname = "currency"
                self.fieldtype = "Link"
                self.options = "Currency"

        result = _from_common_patterns(MockField(), "Sales Invoice")
        default_company = frappe.defaults.get_user_default("Company")
        if default_company:
            expected = frappe.db.get_value("Company", default_company, "default_currency")
            self.assertEqual(result, expected)
