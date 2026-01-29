
import frappe
import requests
import json
import os

def create_custom_ollama_model(model_name, base_model, system_prompt=None, parameters=None, template=None):
    """
    Creates a custom Ollama model with a specialized Modelfile.
    
    Args:
        model_name (str): The name for the new custom model.
        base_model (str): The base model to use (e.g., 'llama3.2').
        system_prompt (str): System prompt to bake into the model.
        parameters (dict): Options like temperature, stop sequences, etc.
        template (str): Custom prompt template.
    """
    settings = frappe.get_single("OwlAI Settings")
    ollama_url = settings.ollama_url or "http://localhost:11434"
    
    modelfile = f"FROM {base_model}\n"
    
    if system_prompt:
        modelfile += f'SYSTEM """{system_prompt}"""\n'
        
    if template:
        modelfile += f'TEMPLATE """{template}"""\n'
        
    if parameters:
        for key, value in parameters.items():
            if isinstance(value, str):
                modelfile += f'PARAMETER {key} "{value}"\n'
            else:
                modelfile += f'PARAMETER {key} {value}\n'
                
    # Use Ollama API to create the model
    # Note: 'create' API is usually streaming/async
    try:
        payload = {
            "name": model_name,
            "modelfile": modelfile
        }
        res = requests.post(f"{ollama_url}/api/create", json=payload, stream=True)
        
        last_status = ""
        for line in res.iter_lines():
            if line:
                status = json.loads(line)
                if status.get("error"):
                    return {"status": "error", "message": status["error"]}
                last_status = status.get("status", "")
                
        return {"status": "success", "message": f"Model '{model_name}' created successfully.", "final_status": last_status}
        
    except Exception as e:
        return {"status": "error", "message": str(e)}

def delete_ollama_model(model_name):
    """Deletes a model from Ollama."""
    settings = frappe.get_single("OwlAI Settings")
    ollama_url = settings.ollama_url or "http://localhost:11434"
    
    try:
        res = requests.delete(f"{ollama_url}/api/delete", json={"name": model_name})
        if res.status_code == 200:
            return {"status": "success"}
        return {"status": "error", "message": res.text}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def push_to_ollama(model_name):
    """Placeholder for future hub integration."""
    pass
