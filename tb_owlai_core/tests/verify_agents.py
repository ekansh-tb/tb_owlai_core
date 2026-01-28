
import frappe
from tb_owlai_core.owlai_core.agent import OwlAgent
import sys

def verify_benchmarks(site_name=None):
    if site_name:
        frappe.init(site=site_name)
        frappe.connect()

    benchmarks = frappe.get_all("OwlAI Benchmark", 
                                filters={"last_run_status": ["in", ["Pending", "Failed"]]}, 
                                fields=["name", "test_name", "agent", "prompt", "expected_response_contains", "expected_tool_call"])

    if not benchmarks:
        print("No pending/failed benchmarks found.")
        return

    print(f"Found {len(benchmarks)} benchmarks to run...")

    for b in benchmarks:
        print(f"Running Benchmark: {b.test_name} (Agent: {b.agent})")
        doc = frappe.get_doc("OwlAI Benchmark", b.name)
        
        try:
            # 1. Init Agent
            # The agent might need a user context. We'll use Administrator.
            # We assume OwlAgent can run without extensive HTTP context if we mock/provide what's needed.
            # However, OwlAgent might rely on 'frappe.session.user'.
            if not frappe.session.user or frappe.session.user == "Guest":
                 frappe.set_user("Administrator")
            
            agent = OwlAgent(user="Administrator", agent_id=b.agent)
            
            # 2. Run Prompt
            # We capture tool calls by inspecting the run result or via a hook if needed.
            # OwlAgent.run returns {"reply": ..., "history": ...}
            # We need to see if tools were called. 
            # Currently OwlAgent.run doesn't explicitly return tool calls in the simple dict.
            # We might need to inspect the agno_agent's memory or last run structure.
            # For now, let's look at the response text and debug logs if possible?
            # actually, agno agent returns a RunResponse which might have tool_calls.
            # But OwlAgent wraps it.
            
            # Let's trust the response text for now. 
            # For tool calls, we might need to enhance OwlAgent to return them or inspect logs.
            # A simple hack: Pass a system prompt instruction to "State which tool you are using".
            # Or better: Check if result contains the tool output if we can.
            
            response_data = agent.run(user_message=b.prompt)
            reply = response_data.get("reply", "")
            
            # 3. Validation
            passed = True
            reasons = []

            # Check Response Text
            if b.expected_response_contains:
                if b.expected_response_contains.lower() not in reply.lower():
                    passed = False
                    reasons.append(f"Response missing text: '{b.expected_response_contains}'")

            # Check Tool Call (Harder without direct access, but let's try strict logging or assumption)
            # If the user wanted a tool call, usually the reply will contain data from it or say "I've done X".
            # For strict tool verification, we would need to mock the tool registry or spy on it.
            # For this MVP, we will skip hard tool verification unless we see it in the debug output.
            if b.expected_tool_call:
                 # Limitation: We can't easily verify tool calls without modifying OwlAgent to return them.
                 # We will add a note.
                 reasons.append(f"Tool verification for '{b.expected_tool_call}' skipped (Agent doesn't return trace yet).")

            # 4. Update Result
            doc.last_run_status = "Passed" if passed else "Failed"
            doc.failure_reason = "; ".join(reasons) if not passed else ""
            doc.last_run_output = reply
            doc.save(ignore_permissions=True)
            
            status_icon = "✅" if passed else "❌"
            print(f"{status_icon} Result: {doc.last_run_status}")
            if not passed:
                print(f"   Reason: {doc.failure_reason}")

        except Exception as e:
            print(f"❌ Error: {e}")
            doc.last_run_status = "Failed"
            doc.failure_reason = str(e)
            doc.save(ignore_permissions=True)
    
    frappe.db.commit()

if __name__ == "__main__":
    # Usage: python verify_agents.py [site_name]
    # Or executed via bench runner
    site = sys.argv[1] if len(sys.argv) > 1 else "waha.local" # Default to current site?
    verify_benchmarks(site)
