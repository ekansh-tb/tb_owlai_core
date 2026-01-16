
import frappe
import sys

def run():
    print("Verifying RAG...")
    try:
        from tb_owlai_core.agno_integrations.tools import FrappeToolkit
        toolkit = FrappeToolkit()
        
        if hasattr(toolkit, "search_knowledge_base"):
             print("✅ search_knowledge_base method exists on Toolkit.")
        else:
             print("❌ search_knowledge_base method MISSING.")

        try:
            import lancedb
            print("✅ LanceDB installed.")
        except ImportError:
            print("❌ LanceDB module not found.")
            
        try:
            import pypdf
            print("✅ pypdf installed.")
        except ImportError:
             print("❌ pypdf module not found.")

    except Exception as e:
        print(f"❌ Error: {e}")

run()
