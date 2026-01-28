
import frappe
import sys
import os

def create_sample_benchmark():
    if not frappe.conf:
        # running standalone
        frappe.init(site="waha.local", sites_path="sites")
        frappe.connect()

    agents = frappe.get_all("OwlAI Agent", pluck="name")
    print(f"Available Agents: {agents}")
    
    test_name = "Test_Basic_Hello"
    if not frappe.db.exists("OwlAI Benchmark", test_name):
        doc = frappe.new_doc("OwlAI Benchmark")
        doc.test_name = test_name
        doc.agent = agents[0] if agents else "Owl Assistant"
        doc.prompt = "Hello, are you ready?"
        doc.expected_response_contains = "ready"
        doc.insert(ignore_permissions=True)
        print("Created benchmark: Test_Basic_Hello")
    else:
        print("Benchmark already exists.")
        
    frappe.db.commit()

if __name__ == "__main__":
    create_sample_benchmark()
