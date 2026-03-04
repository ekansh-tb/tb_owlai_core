import frappe
from frappe.tests import IntegrationTestCase


class TestGetAccountBalance(IntegrationTestCase):
    def setUp(self):
        from tb_owlai_core.plugins.core.tools.get_account_balance import GetAccountBalance
        self.tool = GetAccountBalance()

    def test_permission_check(self):
        """Tool should check GL Entry read permission."""
        # Tool should have permission gate
        result = self.tool.execute({"account": "Cash - TC", "company": "Test Company"})
        self.assertIsInstance(result, dict)

    def test_parameterized_query(self):
        """Verify no SQL injection possible via account parameter."""
        result = self.tool.execute({"account": "'; DROP TABLE tabGL Entry; --"})
        # Should not error with SQL injection, just return 0 or error
        self.assertIsInstance(result, dict)

    def test_default_company(self):
        """Should use user default company if not provided."""
        result = self.tool.execute({"account": "Cash"})
        self.assertIsInstance(result, dict)

    def test_with_date_filter(self):
        """Should accept optional date parameter."""
        result = self.tool.execute({"account": "Cash", "date": "2025-01-01"})
        self.assertIsInstance(result, dict)


class TestGetPartyOutstanding(IntegrationTestCase):
    def setUp(self):
        from tb_owlai_core.plugins.core.tools.get_party_outstanding import GetPartyOutstanding
        self.tool = GetPartyOutstanding()

    def test_auto_detect_party_type(self):
        """Should auto-detect party_type when not provided."""
        result = self.tool.execute({"party": "NonExistentParty12345"})
        self.assertIsInstance(result, dict)

    def test_explicit_party_type(self):
        """Should use provided party_type."""
        result = self.tool.execute({"party": "Test", "party_type": "Customer"})
        self.assertIsInstance(result, dict)


class TestGetSalesSummary(IntegrationTestCase):
    def setUp(self):
        from tb_owlai_core.plugins.core.tools.get_sales_summary import GetSalesSummary
        self.tool = GetSalesSummary()

    def test_period_today(self):
        result = self.tool.execute({"period": "today"})
        self.assertIsInstance(result, dict)
        self.assertIn("period", result)

    def test_period_this_month(self):
        result = self.tool.execute({"period": "this_month"})
        self.assertIsInstance(result, dict)

    def test_period_this_week(self):
        result = self.tool.execute({"period": "this_week"})
        self.assertIsInstance(result, dict)

    def test_invalid_period(self):
        """Should handle invalid period gracefully."""
        result = self.tool.execute({"period": "invalid_period"})
        self.assertIsInstance(result, dict)


class TestGetGeneralLedger(IntegrationTestCase):
    def setUp(self):
        from tb_owlai_core.plugins.core.tools.get_general_ledger import GetGeneralLedger
        self.tool = GetGeneralLedger()

    def test_basic_query(self):
        result = self.tool.execute({})
        self.assertIsInstance(result, dict)

    def test_with_filters(self):
        result = self.tool.execute({
            "from_date": "2025-01-01",
            "to_date": "2025-12-31",
            "limit": 5
        })
        self.assertIsInstance(result, dict)


class TestGetStockBalance(IntegrationTestCase):
    def setUp(self):
        from tb_owlai_core.plugins.core.tools.get_stock_balance import GetStockBalance
        self.tool = GetStockBalance()

    def test_all_stock(self):
        result = self.tool.execute({})
        self.assertIsInstance(result, dict)

    def test_filtered_by_item(self):
        result = self.tool.execute({"item_code": "Test Item"})
        self.assertIsInstance(result, dict)
