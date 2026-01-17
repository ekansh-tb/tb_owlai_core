
import frappe
from werkzeug.wrappers import Response
import json
import base64
import time
import traceback
from litellm import completion
from tb_owlai_core.utils import get_active_provider_config
from tb_owlai_core.tool_registry import ToolRegistry
from tb_owlai_core.owlai_core.agent import OwlAgent
from tb_owlai_core.utils.context import OwlContext
from tb_owlai_core.owlai_core.transcriber import transcribe_to_text

# Conversation memory settings are now in OwlAI Settings

def get_or_create_conversation(conversation_id=None):
    """Get existing conversation or create a new one for current user"""
    user = frappe.session.user
    
    if conversation_id:
        # Load existing conversation
        try:
            conv = frappe.get_doc("OwlAI Conversation", conversation_id)
            # Check permission
            if not conv.has_permission("read"):
                frappe.throw("You don't have permission to access this conversation")
            return conv
        except frappe.DoesNotExistError:
            pass  # Will create new
    
    # Create new conversation
    conv = frappe.get_doc({
        "doctype": "OwlAI Conversation",
        "owner": user,
        "sharing_type": "Private",
        "status": "Active"
    })
    conv.insert(ignore_permissions=True)
    
    # Crucial: Set session_id to the document name to prevent duplication in storage backend
    conv.session_id = conv.name
    conv.save(ignore_permissions=True)
    
    frappe.db.commit()
    return conv


def get_conversation_history(conversation, limit=None):
    """Load last N messages from a conversation for LLM context"""
    if not conversation.messages:
        return []
    
    if limit is None:
        settings = frappe.get_single("OwlAI Settings")
        limit = settings.context_message_limit or 20

    # Get last N messages
    recent_messages = conversation.messages[-limit:] if len(conversation.messages) > limit else conversation.messages
    
    history = []
    for msg in recent_messages:
        if msg.role in ["user", "assistant"]:
            history.append({
                "role": msg.role,
                "content": msg.content
            })
    return history


def save_message(conversation, role, content, message_type="text", action_data=None):
    """Save a message to the conversation"""
    conversation.append("messages", {
        "role": role,
        "content": content[:100000] if content else "",  # Limit content size
        "message_type": message_type,
        "action_data": json.dumps(action_data) if action_data else None
    })
    conversation.message_count = len(conversation.messages)
    conversation.save(ignore_permissions=True)
    frappe.db.commit()






def log_analytics(user, config, model, response_time, prompt_tokens, completion_tokens, total_tokens, status, tool_calls, full_prompt, full_response, error_message=None):
    """Log execution metrics to OwlAI Analytics if enabled"""
    try:
        settings = frappe.get_single("OwlAI Settings")
        if not settings.enable_analytics:
            return

        doc = frappe.get_doc({
            "doctype": "OwlAI Analytics",
            "user": user,
            "timestamp": frappe.utils.now(),
            "status": status,
            "provider": _resolve_provider_link(config.get("provider")),
            "model": _resolve_model_link(model),
            "response_time": response_time,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "tool_calls": json.dumps(tool_calls, indent=2) if tool_calls else None,
            "full_prompt": json.dumps(full_prompt, indent=2) if full_prompt else str(full_prompt),
            "full_response": full_response,
            "error_message": error_message
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception as e:
        print(f"Failed to log analytics: {e}")
        # traceback.print_exc() 
        # Don't throw error to UI for analytics failure

def _resolve_provider_link(provider_identifier):
    """
    Ensures the provider field contains a valid OwlAI Provider name.
    """
    if not provider_identifier: return None
    
    # 1. Direct match
    if frappe.db.exists("OwlAI Provider", provider_identifier):
        return provider_identifier
        
    # 2. Case-insensitive match (e.g. 'ollama' -> 'Ollama')
    provider_name = frappe.db.get_value("OwlAI Provider", 
                                      {"name": ["matches", provider_identifier]}, 
                                      "name")
    if provider_name:
        return provider_name

    # 3. Try partial map or common alises (optional)
    if provider_identifier.lower() == "google": return "Google Gemini"
    
    return None

def _resolve_model_link(model_identifier):
    """
    Ensures the model field contains a valid OwlAI Model name (Link).
    Input could be:
    1. Valid Link Name definition 'qwen2.5:1.5b-Ollama'
    2. LiteLLM identifier 'ollama/qwen2.5:1.5b'
    3. Just model name 'qwen2.5:1.5b'
    """
    if not model_identifier: return None
    
    # 1. Check if valid Link
    if frappe.db.exists("OwlAI Model", model_identifier):
        return model_identifier
        
    # 2. Try to reverse lookup by model_name
    # Handle 'provider/model' format
    search_name = model_identifier
    if "/" in model_identifier:
        search_name = model_identifier.split("/", 1)[1]
    
    # Simple search
    found = frappe.db.get_value("OwlAI Model", {"model_name": search_name}, "name")
    if found: return found
    
    # 3. Try fuzzy search if strict match fails (optional, maybe overkill?)
    
    # If not found, return None to avoid LinkValidationError since field is not mandatory
    return None



@frappe.whitelist()
def handle_stream_input(route=None, text=None, conversation_id=None, context=None, mode=None):
    """
    Streaming chat handler (SSE).
    """
    user = frappe.session.user
    
    # Debug log for 500 error diagnosis
    # frappe.log_error("OWL DEBUG: handle_stream_input called")
    
    try:
        conversation = get_or_create_conversation(conversation_id)
        if route and not conversation.context_route:
            conversation.context_route = route
            conversation.save(ignore_permissions=True)
        
        _update_conversation_title(conversation, text, None, None)

        context_data = {}
        if context:
            try:
                 context_data = json.loads(context)
            except: pass
        current_route = route or context_data.get('route')
        
        from tb_owlai_core.agno_integrations.main import get_agent
        
        additional_context = f"""
        Current Context:
        - Route: {current_route or 'Unknown'}
        - Form Data: {json.dumps(context_data.get('form_data') or {})}
        - Selected Items: {json.dumps(context_data.get('selected_items') or [])}
        User: {user}
        """
        
        agent = get_agent(conversation_id=conversation.name)
        
        def generate():
            full_response_text = ""
            start_time = time.time()
            status = "Success"
            error_message = None
            tool_calls = [] 
            
            try:
                # Yield Start Event
                yield f"event: start\ndata: {json.dumps({'conversation_id': conversation.name})}\n\n"

                stream = agent.run(text, additional_context=additional_context, stream=True)
                
                if stream:
                    for chunk in stream:
                        # 1. Capture content tokens
                        token = ""
                        if hasattr(chunk, "content") and chunk.content:
                             token = chunk.content
                        elif isinstance(chunk, str):
                             token = chunk
                        
                        # 2. Capture Tool Calls if present in this chunk
                        current_tool_calls = []
                        if hasattr(chunk, "tools") and chunk.tools:
                            for t in chunk.tools:
                                tool_call = {"name": t.tool_name, "parameters": t.tool_args}
                                tool_calls.append(tool_call) # For analytics
                                current_tool_calls.append(tool_call)

                        # Yield data
                        payload = {}
                        if token: payload["token"] = token
                        if current_tool_calls: payload["action_data"] = current_tool_calls
                        
                        if payload:
                            yield f"data: {json.dumps(payload)}\n\n"
                            if token: full_response_text += token
                
            except Exception as e:
                status = "Error"
                error_message = str(e)
                # Yield error as a normal token so it appears in the chat UI
                friendly_error = f"\n\n**I encountered an error:** {str(e)}\nPlease check the logs or try again."
                yield f"data: {json.dumps({'token': friendly_error})}\n\n"
                
                # Also yield the actual error event for checking
                yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
                frappe.log_error(title="Stream Error", message=traceback.format_exc())
                
            finally:
                duration = time.time() - start_time
                try:
                    log_analytics(
                        user=user,
                        config={},
                        model=agent.model.id if agent and agent.model else "Unknown",
                        response_time=duration,
                        prompt_tokens=0, 
                        completion_tokens=len(full_response_text)/4,
                        total_tokens=0,
                        status=status,
                        tool_calls=tool_calls,
                        full_prompt=text,
                        full_response=full_response_text,
                        error_message=error_message
                    )
                except: pass
                
                yield "event: end\ndata: [DONE]\n\n"

        return Response(generate(), mimetype='text/event-stream')
        
    except Exception as top_e:
        import traceback
        error_msg = f"Fatal 500 Error in handle_stream_input: {str(top_e)}\n{traceback.format_exc()}"
        frappe.log_error(title="OwlAI Stream Error", message=error_msg)
        # Return a Response with error if possible, or re-raise to see it in logs
        return Response(f"event: error\ndata: {json.dumps({'error': str(top_e)})}\n\n", 
                        status=500, mimetype='text/event-stream')


@frappe.whitelist()
def handle_input_v2(route=None, text=None, conversation_id=None, context=None, mode=None):
    """
    Main chat handler using the new Agent Architecture.
    Accepts:
    - route: Current route string (legacy, also in context)
    - text: User query
    - conversation_id: ID to continue
    - context: JSON string containing frontend context (form_data, selection, etc.)
    - mode: 'single' (Action) or 'agentic' (Multi-step)
    """
    user = frappe.session.user
    
    # 2. Get or create conversation
    conversation = get_or_create_conversation(conversation_id)
    if route and not conversation.context_route:
        conversation.context_route = route
        conversation.save(ignore_permissions=True)
    
    # 3. Handle Files
    files = frappe.request.files
    image_file = files.get('image')
    audio_file = files.get('audio')
    
    # Process Audio immediately if present
    if audio_file:
        transcribed_text = transcribe_to_text(audio_file)
        if transcribed_text.startswith("Error"):
             return {"reply": f"⚠️ Audio Transcription Failed: {transcribed_text}"}
        
        # Determine if we append or replace
        if text:
            text += f"\n(Transcribed Info: {transcribed_text})"
        else:
            text = transcribed_text
    
    # Update Title if needed
    _update_conversation_title(conversation, text, image_file, audio_file)

    # 4. Prepare Context
    context_data = {}
    if context:
        try:
             context_data = json.loads(context)
        except: pass
    
    # If route is passed separately, prefer it or fallback to context
    current_route = route or context_data.get('route')
    
    # Instantiate OwlContext
    # This class robustly handles route parsing and data extraction
    agent_context = OwlContext(
        route=current_route,
        form_data=context_data.get('form_data'),
        selected_items=context_data.get('selected_items')
    )
    

    
    
    # 5. Instantiate and Run Agent (Agno)
    from tb_owlai_core.agno_integrations.main import get_agent
    
    # Prepare additional context from OwlContext
    # We serialize what we know about the current view
    additional_context = f"""
    Current Context:
    - Route: {current_route or 'Unknown'}
    - Form Data: {json.dumps(context_data.get('form_data') or {})}
    - Selected Items: {json.dumps(context_data.get('selected_items') or [])}
    User: {user}
    """
    
    # Agent Configuration
    # We can pass agent_id if we have one selected in settings, or passed in request
    # For now, default agent.
    
    try:
        agent = get_agent(
            conversation_id=conversation.name,
            # agent_id=settings.default_agent # TODO: Add this to get_agent logic if needed
        )
    except Exception as e:
         frappe.log_error(title="Agent Definition Error", message=traceback.format_exc())
         return {"reply": f"⚠️ Failed to initialize AI Agent: {str(e)}"}

    start_time = time.time()
    status = "Success"
    error_message = None
    
    try:
        # Run OwlAi Agent
        # We pass the user Query (text) and context
        
        # Handling images if supported by Agno (TODO: Check Image artifact support in get_agent config)
        # For now, text only.
        
        response = agent.run(
             text,
             additional_context=additional_context
             # images=[image_file] if image_file else None # Agno needs Image object wrapper
        )
        
        # Response is RunOutput
        reply = response.content
        
        # Determine action_data for Frontend
        action_data = None
        
        # 1. Native Tool Calls
        if response.tools:
            action_data = []
            for t in response.tools:
                action_data.append({
                    "name": t.tool_name,
                    "parameters": t.tool_args
                })
        
        # 2. Fallback: Parse JSON from reply
        if not action_data and reply and reply.strip().startswith("{"):
            try:
                possible = json.loads(reply)
                if "name" in possible and "parameters" in possible:
                    action_data = possible
                    # Clear reply so we don't show raw JSON to user
                    reply = ""
            except: pass

        result = {"reply": reply, "action_data": action_data}
        
    except Exception as e:
        status = "Error"
        error_message = str(traceback.format_exc())
        frappe.log_error("OwlAI OwlAi Agent Error")
        result = {"reply": f"An error occurred: {str(e)}"}
        response = None
        
    finally:
        end_time = time.time()
        duration = end_time - start_time
        
        # Log Analytics
        try:
            metrics = response.metrics if response and response.metrics else None
            
            tool_calls = []
            # Extract tool calls from response tools list
            if response and response.tools:
                 for t in response.tools:
                     tool_calls.append({
                         "name": t.tool_name,
                         "args": t.tool_args,
                         "result": str(t.result)[:1000] # Truncate result
                     })
            
            log_analytics(
                user=user,
                config={}, # Agno config not easily accessible as dict, pass empty or reconstruct
                model=agent.model.id if agent and agent.model else "Unknown",
                response_time=duration,
                prompt_tokens=metrics.input_tokens if metrics else 0,
                completion_tokens=metrics.output_tokens if metrics else 0,
                total_tokens=metrics.total_tokens if metrics else 0,
                status=status,
                tool_calls=tool_calls,
                full_prompt=text,
                full_response=result.get("reply", ""),
                error_message=error_message
            )
        except Exception as log_e:
             # print(f"Analytics Error: {log_e}")
             pass

    # result contains {"reply": "..."}
    # Add conversation_id for frontend tracking
    result["conversation_id"] = conversation.name
    
    return result

def _update_conversation_title(conversation, text, image_file, audio_file):
    """Helper to name the conversation, including context where possible"""
    title_text = text or ""
    if not title_text.strip():
        if image_file: title_text = "Image Analysis"
        elif audio_file: title_text = "Voice Command"
    
    # Valid title update conditions
    should_update = False
    if not conversation.title:
        should_update = True
    elif conversation.title == conversation.name:
        should_update = True
    elif conversation.title.startswith("Conversation "):
        should_update = True
    elif "OWL-CONV-" in conversation.title:
        should_update = True
    elif conversation.title == "New Conversation":
        should_update = True

    if title_text and should_update:
        # Clean title text
        title = title_text.strip().split('\n')[0]
        title = title[:60] + "..." if len(title) > 60 else title
        
        # Add contextual suffix if it's a generic command
        if conversation.context_route and " " not in title:
             title = f"{title} ({conversation.context_route.split('/')[-1]})"

        conversation.title = title
        conversation.save(ignore_permissions=True)
        frappe.db.commit()


@frappe.whitelist()
def update_owlai_settings(model=None, api_key=None, enable_analytics=None):
    """Update settings directly from Chat UI"""
    if not frappe.session.user: return
    settings = frappe.get_single("OwlAI Settings")
    if model:
        if "gemini" in model.lower():
             settings.gemini_model = model
             settings.provider = "Generative AI (Gemini)"
    if api_key:
        settings.gemini_api_key = api_key
    
    if enable_analytics is not None:
        settings.enable_analytics = int(enable_analytics)

    settings.save(ignore_permissions=True)
    frappe.db.commit()
    return {"status": "success"}


@frappe.whitelist()
def get_conversations(limit=20, search_text=None):
    user = frappe.session.user
    filters = {"status": "Active"}
    
    if search_text:
        filters["title"] = ["like", f"%{search_text}%"]

    return frappe.get_all("OwlAI Conversation",
        filters=filters,
        or_filters=[["owner", "=", user], ["sharing_type", "=", "Public"]],
        fields=["name", "title", "modified"],
        order_by="modified desc",
        limit=limit
    )


@frappe.whitelist()
def new_conversation():
    conv = get_or_create_conversation()
    return {"conversation_id": conv.name}

@frappe.whitelist()
def delete_conversation(conversation_id):
    if not conversation_id: return
    try:
        frappe.delete_doc("OwlAI Conversation", conversation_id)
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@frappe.whitelist()
def update_conversation_title(conversation_id, title):
    if not conversation_id or not title: return
    try:
        frappe.db.set_value("OwlAI Conversation", conversation_id, "title", title)
        return {"status": "success"}
    except Exception as e:
        frappe.log_error(title="Error updating title", message=traceback.format_exc())
        return {"status": "error", "message": str(e)}

@frappe.whitelist()
def get_conversation_messages(conversation_id):
    if not conversation_id: return []
    try:
        conv = frappe.get_doc("OwlAI Conversation", conversation_id)
        if not conv.has_permission("read"): return []
        
        messages = []
        for m in conv.messages:
            try:
                action_data = json.loads(m.action_data) if m.action_data else None
            except:
                action_data = None

            messages.append({
                "role": m.role,
                "content": m.content,
                "message_type": m.message_type,
                "creation": m.creation,
                "idx": m.idx,
                "action_data": action_data
            })
        return messages
    except:
        return []

@frappe.whitelist()
def get_conversation_info(conversation_id):
    if not conversation_id: return None
    try:
        conv = frappe.get_doc("OwlAI Conversation", conversation_id)
        if not conv.has_permission("read"): return None
        return {
            "name": conv.name,
            "title": conv.title,
            "status": conv.status,
            "modified": conv.modified
        }
    except:
        return None
