import frappe
from tb_owlai_core.owlai_core.doctype.owlai_knowledge_base.owlai_knowledge_base import add_to_index

def run():
    failed_docs = frappe.get_all("OwlAI Knowledge Base", filters={"status": "Failed"}, fields=["name"])
    print(f"Found {len(failed_docs)} failed documents.")
    
    for d in failed_docs:
        print(f"Re-indexing {d.name}...")
        try:
            # We call add_to_index directly (sync) to see output
            add_to_index(d.name)
            print(f"✅ Success: {d.name}")
        except Exception as e:
            print(f"❌ Failed again: {d.name} - {e}")

    # Also re-index Pending ones if any stuck
    pending_docs = frappe.get_all("OwlAI Knowledge Base", filters={"status": "Pending"}, fields=["name"])
    for d in pending_docs:
        print(f"Indexing Pending {d.name}...")
        try:
            add_to_index(d.name)
            print(f"✅ Success: {d.name}")
        except Exception as e:
            print(f"❌ Failed: {d.name} - {e}")

if __name__ == "__main__":
    run()
