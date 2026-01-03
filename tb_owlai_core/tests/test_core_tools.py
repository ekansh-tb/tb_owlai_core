import frappe
from frappe.tests.utils import FrappeTestCase
from tb_owlai_core.tool_registry import ToolRegistry

class TestCoreTools(FrappeTestCase):
    def setUp(self):
        self.registry = ToolRegistry()
        # Ensure ToDo exists for testing
        if not frappe.db.exists("ToDo", "Test Tool ToDo"):
             frappe.get_doc({"doctype": "ToDo", "description": "Test Tool ToDo", "status": "Open"}).insert()

    def test_tool_discovery(self):
        tools = self.registry.get_available_tools()
        names = [t['name'] for t in tools]
        self.assertIn("create_document", names)
        self.assertIn("list_documents", names)

    def test_list_documents(self):
        result = self.registry.execute_tool("list_documents", {
            "doctype": "ToDo", 
            "filters": {"description": "Test Tool ToDo"},
            "limit_page_length": 1
        })
        self.assertTrue(result.get("data"))
        self.assertEqual(result.get("doctype"), "ToDo")
        self.assertEqual(result.get("action"), "list")

    def test_get_doctype_info(self):
        result = self.registry.execute_tool("get_doctype_info", {"doctype": "ToDo"})
        self.assertTrue(result.get("fields"))
        self.assertIn("description", [f['fieldname'] for f in result['fields']])

    def tearDown(self):
        # Clean up
        frappe.db.rollback()
