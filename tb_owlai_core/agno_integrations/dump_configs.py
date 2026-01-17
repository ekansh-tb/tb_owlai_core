import frappe
import json
import os

def dump():
    configs = {}
    
    # OwlAI Settings
    try:
        configs["OwlAI Settings"] = frappe.get_single("OwlAI Settings").as_dict()
    except Exception as e:
        configs["OwlAI Settings"] = str(e)
        
    # OwlAI Agent
    try:
        configs["OwlAI Agent"] = frappe.get_all("OwlAI Agent", fields="*")
    except Exception as e:
        configs["OwlAI Agent"] = str(e)
        
    # OwlAI Model
    try:
        configs["OwlAI Model"] = frappe.get_all("OwlAI Model", fields="*")
    except Exception as e:
        configs["OwlAI Model"] = str(e)
        
    # OwlAI Tool
    try:
        configs["OwlAI Tool"] = frappe.get_all("OwlAI Tool", fields="*")
    except Exception as e:
        configs["OwlAI Tool"] = str(e)
        
    # OwlAI Provider
    try:
        configs["OwlAI Provider"] = frappe.get_all("OwlAI Provider", fields="*")
    except Exception as e:
        configs["OwlAI Provider"] = str(e)

    # Write to file with absolute path
    path = "/Users/ekanshjain/Work/TechBird/frappe-bench/owlai_configs_dump.json"
    with open(path, "w") as f:
        json.dump(configs, f, indent=4, default=str)
    
    print(f"Dumped to {path}")

if __name__ == "__main__":
    dump()
