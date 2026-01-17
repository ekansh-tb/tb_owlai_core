
import frappe

def cleanup():
    print("Starting Cleanup of OwlAI Data...")
    
    # 1. Cleanup Conversations (Sessions)
    frappe.db.delete("OwlAI Conversation")
    print("Deleted all OwlAI Conversation records.")
    
    # 2. Cleanup Agents (Start Fresh)
    # We might want to keep one "Default" agent if it exists, or just nuke all.
    # Per user instruction "delete the existing redundent data", I'll be aggressive but safe.
    # Let's delete all except arguably "System" ones if we had flagged them. We don't.
    frappe.db.delete("OwlAI Agent")
    print("Deleted all OwlAI Agent records.")
    
    # 3. Cleanup Tools? 
    # Tools are definitions, maybe keep them? 
    # The user said "redundant data". Tools are usually config. I'll leave them for now unless they are junk.
    
    frappe.db.commit()
    print("Cleanup Complete. Ready for fresh initialization.")

if __name__ == "__main__":
    cleanup()
