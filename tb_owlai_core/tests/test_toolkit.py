
import frappe
from tb_owlai_core.agno_integrations.tools import FrappeToolkit

def test_toolkit_filtering():
    print("Testing FrappeToolkit Filtering...")
    
    # 1. Test All Tools
    tk_all = FrappeToolkit()
    # Agno Toolkit usually stores tools in .tools, which is a dict or list of Functions
    print(f"Toolkit properties: {dir(tk_all)}")
    
    # Try accessing functions
    if hasattr(tk_all, "functions"):
        all_funcs = list(tk_all.functions.keys())
    else:
        print("ERROR: Toolkit has no 'functions' attribute")
        return

    print(f"All Tools Count: {len(all_funcs)}")
    if "list_documents" in all_funcs:
        print("PASS: list_documents present by default.")
    
    # 2. Test Filtering
    tk_filtered = FrappeToolkit(selected_tools=["get_document", "navigate"])
    
    if hasattr(tk_filtered, "functions"):
        filtered_funcs = list(tk_filtered.functions.keys())
    else:
        filtered_funcs = []
        
    print(f"Filtered Tools: {filtered_funcs}")
    
    if "list_documents" not in filtered_funcs:
        print("PASS: list_documents excluded.")
    if "get_document" in filtered_funcs:
        print("PASS: get_document included.")
        
test_toolkit_filtering()
