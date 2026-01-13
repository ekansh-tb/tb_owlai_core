
import frappe
from tb_owlai_core.utils.plugin_manager import PluginManager
from tb_owlai_core.plugins.core.plugin import CorePlugin

def debug():
    print("--- Debugging Tool Discovery ---")
    pm = PluginManager()
    
    # 1. Check Core Plugin Tools List
    print("Instantiating CorePlugin directly...")
    plugin = CorePlugin(pm)
    tools = plugin.get_tools()
    print(f"CorePlugin.get_tools() returned: {tools}")
    
    if "navigate" not in tools:
        print("CRITICAL: 'navigate' is missing from get_tools()! The file update might not have persisted or is cached.")
    else:
        print("'navigate' IS in get_tools().")

    # 2. Try to load 'navigate' manually
    print("\nAttempting to import navigate tool module...")
    try:
        import importlib
        mod = importlib.import_module("tb_owlai_core.plugins.core.tools.navigate")
        print(f"Successfully imported module: {mod}")
        
        # Check class
        found = False
        for attr_name in dir(mod):
            attr = getattr(mod, attr_name)
            try:
                if hasattr(attr, "name") and attr.name == "navigate": # heuristic
                     print(f"Found tool class/instance: {attr}")
                     found = True
            except: pass
        if not found:
             print("Could not find tool class in module.")

    except Exception as e:
        print(f"Import failed: {e}")

    # 3. Check PluginManager state
    print("\nPluginManager State:")
    print(f"Loaded plugins: {list(pm.plugins.keys())}")
    print(f"Loaded tools: {list(pm.tools.keys())}")
    
    if "navigate" in pm.tools:
        print("PluginManager HAS 'navigate' loaded.")
    else:
        print("PluginManager DOES NOT have 'navigate'.")

if __name__ == "__main__":
    debug()
