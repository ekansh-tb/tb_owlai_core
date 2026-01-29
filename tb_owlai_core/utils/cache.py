
import frappe
import json
import hashlib

class OwlCache:
    """
    Utility for caching tool results and LLM responses to speed up local LLM interactions.
    """
    
    @staticmethod
    def get_key(namespace, data):
        """Generate a unique key for a namespace and any serializable data."""
        if isinstance(data, (dict, list)):
            data_str = json.dumps(data, sort_keys=True)
        else:
            data_str = str(data)
        
        hash_val = hashlib.md5(data_str.encode()).hexdigest()
        return f"owlai:{namespace}:{hash_val}"

    @staticmethod
    def get(namespace, data):
        key = OwlCache.get_key(namespace, data)
        return frappe.cache().get_value(key)

    @staticmethod
    def set(namespace, data, value, expires_in_sec=3600):
        key = OwlCache.get_key(namespace, data)
        frappe.cache().set_value(key, value, expires_in_sec=expires_in_sec)

    @staticmethod
    def clear(namespace=None):
        if namespace:
            frappe.cache().delete_keys(f"owlai:{namespace}:*")
        else:
            frappe.cache().delete_keys("owlai:*")

def cache_tool_result(expires_in_sec=3600):
    """Decorator to cache tool results."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # args[0] is usually 'self' (the toolkit or registry)
            # We skip 'self' and use func name + logic to cache
            cache_data = {"args": args[1:], "kwargs": kwargs}
            cached = OwlCache.get(func.__name__, cache_data)
            if cached is not None:
                return cached
            
            result = func(*args, **kwargs)
            OwlCache.set(func.__name__, cache_data, result, expires_in_sec)
            return result
        return wrapper
    return decorator
