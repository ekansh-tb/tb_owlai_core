
import frappe
import traceback

def run():
    print("Verifying RAG Imports Deeply...")
    try:
        from tb_owlai_core.agno_integrations import knowledge_index
        print("✅ Successfully imported knowledge_index module.")
        
        # Check attributes
        if hasattr(knowledge_index, "OllamaEmbedder"):
             print("✅ OllamaEmbedder found in module.")
        
        if hasattr(knowledge_index, "get_vector_db"):
             print("✅ get_vector_db function found.")

    except ImportError as e:
        print(f"❌ ImportError: {e}")
        traceback.print_exc()
    except Exception as e:
        print(f"❌ Error: {e}")
        traceback.print_exc()

run()
