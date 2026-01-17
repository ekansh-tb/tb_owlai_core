
import frappe

def list_tools():
    tools = frappe.get_all("OwlAI Tool", fields=["name", "tool_name", "type", "method_path"])
    print(f"Found {len(tools)} tools:")
    for t in tools:
        print(f" - Name: {t.name}, Tool Name: {t.tool_name}, Type: {t.type}, Path: {t.method_path}")

if __name__ == "__main__":
    list_tools()
