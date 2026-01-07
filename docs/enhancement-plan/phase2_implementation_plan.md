# OwlAI Core Improvement Plan - Phase 2: Logic Integration

**Objective**: Integrate the newly created Phase 1 DocTypes (`OwlAI Agent`, `OwlAI Model`, `OwlAI Tool`, `OwlAI Provider`) into the core logic of `agent.py` and `tool_registry.py`.

## Phase 1 Review (Completed)
- [x] Created `OwlAI Model` DocType
- [x] Created `OwlAI Agent` DocType
- [x] Created `OwlAI Tool` DocType
- [x] Created `OwlAI Provider` DocType
- [x] Created `OwlAI Agent Tool` Child Table

## Phase 2 Tasks (Execution)

### 1. Update `tool_registry.py`
- [x] Modify `ToolRegistry` to verify if tools exist in `OwlAI Tool`.
- [x] If `OwlAI Tool` records are missing for built-in tools, auto-create them on startup or access.
- [x] Allow fetching tools based on `OwlAI Agent` configuration.

### 2. Refactor `agent.py`
- [x] Update `__init__` to accept an `agent_id` (or name) to load the specific `OwlAI Agent` document.
- [x] Use `OwlAI Agent` properties for:
    - `system_prompt`
    - `model` (Link to `OwlAI Model`)
    - `max_steps` (if added to doctype)
    - `tools` (Link to `OwlAI Agent Tool`)
- [x] Update `get_system_prompt` to use the agent-specific prompt.
- [x] Update `run` loop to use the model/provider defined in the `OwlAI Agent` -> `OwlAI Model` -> `OwlAI Provider` chain.

### 3. Update `utils.py` (or `provider.py`)
- [x] Create/Update logic to fetch credentials/config from `OwlAI Provider` and `OwlAI Model` instead of just `OwlAI Settings`.
- [x] Ensure backward compatibility or migration from `OwlAI Settings` if needed.

### 4. Updates to `OwlAI Settings`
- [x] Add a default `OwlAI Agent` field to the settings, so the chat interface knows which agent to load by default.

### 5. Migration Script
- [x] Create a patch to populate `OwlAI Tool` with existing system tools.
- [x] Create a default "General Assistant" `OwlAI Agent` and link it in settings.

## Success Criteria
- [ ] `OwlAgent` initializes using an `OwlAI Agent` document.
- [ ] Tools are filtered based on the Agent's allowed tools.
- [ ] LLM calls use the specific Model/Provider defined for that Agent.
