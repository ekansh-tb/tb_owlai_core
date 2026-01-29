import frappe
from langchain_openai import ChatOpenAI
from langchain_community.chat_models import ChatOllama
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq

def get_llm(model_name):
    """
    Returns a configured LangChain Chat Model based on OwlAI Model document.
    """
    if not model_name:
        return None
        
    model_doc = frappe.get_doc("OwlAI Model", model_name)
    provider_doc = frappe.get_doc("OwlAI Provider", model_doc.provider)
    
    api_key = provider_doc.get_password("api_key")
    base_url = provider_doc.api_base
    
    # Provider Logic
    if provider_doc.provider_name == "OpenAI":
        return ChatOpenAI(
            model=model_doc.model_name,
            api_key=api_key,
            base_url=base_url if base_url else None,
            temperature=0.7
        )
        
    elif provider_doc.provider_name == "Ollama":
        return ChatOllama(
            model=model_doc.model_name,
            base_url=base_url or "http://localhost:11434",
            temperature=0.7
        )
        
    elif provider_doc.provider_name == "Anthropic":
        return ChatAnthropic(
            model_name=model_doc.model_name,
            api_key=api_key,
            temperature=0.7
        )
        
    elif provider_doc.provider_name == "Groq":
        return ChatGroq(
            model_name=model_doc.model_name,
            api_key=api_key,
            temperature=0.7
        )

    elif provider_doc.provider_name == "Google Gemini":
        return ChatGoogleGenerativeAI(
            model=model_doc.model_name,
            google_api_key=api_key,
            temperature=0.7
        )

    else:
        frappe.throw(f"Unsupported Provider: {provider_doc.provider_name}")
