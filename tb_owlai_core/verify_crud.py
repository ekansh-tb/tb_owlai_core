import frappe
from tb_owlai_core.plugins.core.tools.create_document import CreateDocument
from tb_owlai_core.plugins.core.tools.update_document import UpdateDocument
from tb_owlai_core.plugins.core.tools.delete_document import DeleteDocument
from tb_owlai_core.plugins.core.tools.get_document import GetDocument
from tb_owlai_core.plugins.core.tools.list_documents import ListDocuments
from tb_owlai_core.plugins.core.tools.frappe_utils import FrappeUtilsTool

def test():
    print("--- Testing CRUD Tools ---")
    
    # 1. Create
    print("\n1. Testing CreateDocument...")
    create_tool = CreateDocument()
    # Using 'Note' doctype as it's safe and standard
    args = {
        "doctype": "Note",
        "data": {
            "title": "OwlAI Test Note",
            "content": "This is a test note created by OwlAI generic tools."
        }
    }
    result = create_tool.execute(args)
    print(f"Result: {result}")
    
    if "error" in result:
        print("Create failed!")
        return

    docname = result["name"]
    
    # 2. Get
    print("\n2. Testing GetDocument...")
    get_tool = GetDocument()
    result = get_tool.execute({"doctype": "Note", "name": docname})
    print(f"Result (Title): {result.get('title')}")
    
    if result.get("title") != "OwlAI Test Note":
        print("Get failed or mismatch!")

    # 3. Update
    print("\n3. Testing UpdateDocument...")
    update_tool = UpdateDocument()
    result = update_tool.execute({
        "doctype": "Note", 
        "name": docname,
        "data": {"content": "Updated content by OwlAI."}
    })
    print(f"Result: {result}")
    
    # Verify Update
    doc = frappe.get_doc("Note", docname)
    print(f"Verified Content: {doc.content}")

    # 4. List
    print("\n4. Testing ListDocuments...")
    list_tool = ListDocuments()
    result = list_tool.execute({
        "doctype": "Note", 
        "filters": {"title": "OwlAI Test Note"}
    })
    print(f"Result Count: {result.get('count')}")

    # 5. Generic Utils
    print("\n5. Testing FrappeUtilsTool...")
    utils_tool = FrappeUtilsTool()
    result = utils_tool.execute({
        "function": "format_date",
        "args": ["2026-01-01"], 
        "kwargs": {"format_string": "dd-MM-yyyy"}
    })
    print(f"Result (Date): {result}")
    
    # 6. Delete
    print("\n6. Testing DeleteDocument...")
    delete_tool = DeleteDocument()
    result = delete_tool.execute({"doctype": "Note", "name": docname})
    print(f"Result: {result}")

    # Verify Delete
    if not frappe.db.exists("Note", docname):
        print("Verified Deletion: Document gone.")
    else:
        print("Verified Deletion: Document STILL EXISTS!")

