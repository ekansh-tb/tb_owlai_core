/**
 * 🦉 OwlAI Global Mount
 * Enhanced "Spotlight Search" Style Interface for Frappe Desk.
 * Designed to look like a native part of Frappe Desk with Premium Aesthetics.
 */

class OwlMount {
    constructor() {
        this.is_open = false;
        this.is_minimized = false;
        this.mount_point_id = "owl-spotlight-wrapper";
        this.markdown_loaded = false;

        // Conversation persistence — survive minimize/close cycles
        this.conversation_id = sessionStorage.getItem('owlai_conversation_id') || null;
        this._last_route = sessionStorage.getItem('owlai_last_route') || null;

        if (typeof frappe !== 'undefined') {
            frappe.run_serially([
                () => this.load_markdown_lib(),
                () => this.init()
            ]);
        }
    }

    async load_markdown_lib() {
        if (typeof marked !== 'undefined') {
            this.markdown_loaded = true;
            return;
        }
        try {
            await frappe.require("https://cdn.jsdelivr.net/npm/marked/marked.min.js");
            this.markdown_loaded = true;
        } catch (e) {
            console.warn("OwlAI: Could not load marked.js", e);
        }
    }

    init() {
        console.log("🦉 OwlAI Spotlight: Synced with Frappe Desk core.");
        this.inject_styles();
        this.bind_shortcuts();
        this.mount_navbar_trigger();
    }

    inject_styles() {
        if (document.getElementById('owl-spotlight-styles')) return;
        const style = document.createElement('style');
        style.id = 'owl-spotlight-styles';
        style.textContent = `
            #owl-spotlight-wrapper {
                position: fixed;
                top: 0; left: 0; width: 100vw; height: 100vh;
                z-index: 9999;
                display: flex;
                align-items: flex-start;
                justify-content: center;
                padding-top: 15vh;
                background: rgba(var(--overlay-bg, 0, 0, 0), 0.2);
                backdrop-filter: blur(8px);
                opacity: 0;
                pointer-events: none;
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            }
            #owl-spotlight-wrapper.active {
                opacity: 1;
                pointer-events: auto;
            }
            
            /* Minimized State - Floating Widget */
            #owl-spotlight-wrapper.minimized {
                background: transparent;
                backdrop-filter: none;
                pointer-events: none;
                justify-content: flex-end;
                align-items: flex-end;
                padding-top: 0;
            }
            
            #owl-spotlight-wrapper.minimized #owl-spotlight-modal {
                width: 400px;
                max-height: 500px;
                margin: 24px;
                pointer-events: auto;
                transform: translateY(0) scale(1);
                box-shadow: var(--shadow-xl, 0 20px 25px -5px rgba(0,0,0,0.1));
                border: 1px solid var(--border-color);
            }
            
            #owl-spotlight-wrapper.minimized .owl-spotlight-glow {
                display: none;
            }

            .owl-spotlight-glow {
                position: absolute;
                width: 600px;
                height: 600px;
                background: radial-gradient(circle, var(--fg-color, #6366f1) 0%, transparent 70%);
                opacity: 0.15;
                top: -300px;
                left: 50%;
                transform: translateX(-50%);
                pointer-events: none;
                z-index: -1;
                filter: blur(60px);
            }

            #owl-spotlight-modal {
                width: 720px;
                max-width: 90vw;
                max-height: 70vh;
                background: var(--card-bg, #fff);
                border: 1px solid var(--border-color, #e2e8f0);
                box-shadow: var(--shadow-2xl, 0 25px 50px -12px rgba(0,0,0,0.25));
                border-radius: 12px;
                display: flex;
                flex-direction: column;
                overflow: hidden;
                transform: scale(0.98) translateY(10px);
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                font-family: inherit;
            }
            #owl-spotlight-wrapper.active #owl-spotlight-modal {
                transform: scale(1) translateY(0);
            }

            .owl-bar {
                display: flex;
                align-items: center;
                padding: 16px 20px;
                border-bottom: 1px solid var(--border-color);
                background: var(--bg-color);
            }
            .owl-search-icon {
                color: var(--primary-color);
                margin-right: 14px;
                display: flex;
                align-items: center;
            }
            .owl-input {
                flex: 1;
                background: transparent;
                border: none;
                color: var(--text-color);
                font-size: 18px;
                outline: none;
                font-weight: 400;
            }
            .owl-input::placeholder {
                color: var(--text-muted);
                opacity: 0.5;
            }

            .owl-header-actions {
                display: flex;
                gap: 4px;
            }
            .owl-action-btn {
                background: transparent;
                border: none;
                color: var(--text-muted);
                width: 30px; height: 30px;
                border-radius: 6px;
                display: flex;
                align-items: center;
                justify-content: center;
                cursor: pointer;
                transition: background 0.2s;
            }
            .owl-action-btn:hover {
                background: var(--bg-hover-color);
                color: var(--text-color);
            }

            .owl-content {
                flex: 1;
                overflow-y: auto;
                min-height: 80px;
                max-height: 50vh;
                display: flex;
                flex-direction: column;
                background: var(--bg-color);
            }
            
            .owl-message {
                padding: 16px 20px;
                border-bottom: 1px solid var(--border-color);
                font-size: 14px;
                line-height: 1.6;
                color: var(--text-color);
                animation: owlFadeIn 0.3s ease both;
            }
            .owl-message.user {
                background: var(--subtle-accent, #f8fafc);
                font-weight: 500;
            }
            .owl-message.assistant {
                background: transparent;
            }
            .owl-message.system {
                color: var(--text-muted);
                font-size: 12px;
                padding: 12px 20px;
                text-align: center;
                background: var(--bg-light-gray);
            }

            .owl-typing-indicator {
                display: flex;
                gap: 4px;
                padding: 16px 20px;
                align-items: center;
            }
            .owl-dot {
                width: 4px; height: 4px;
                background: var(--primary-color);
                border-radius: 50%;
                opacity: 0.6;
                animation: owlPulse 1.2s infinite;
            }
            .owl-dot:nth-child(2) { animation-delay: 0.2s; }
            .owl-dot:nth-child(3) { animation-delay: 0.4s; }

            @keyframes owlFadeIn {
                from { opacity: 0; transform: translateY(4px); }
                to { opacity: 1; transform: translateY(0); }
            }
            @keyframes owlPulse {
                0%, 100% { opacity: 0.3; transform: scale(0.8); }
                50% { opacity: 1; transform: scale(1.1); }
            }

            .owl-trigger-icon-svg {
                transition: transform 0.2s ease;
                fill: var(--text-muted);
            }
            #owl-navbar-trigger:hover .owl-trigger-icon-svg {
                transform: scale(1.1);
                fill: var(--primary-color);
            }
            
            .hidden { display: none !important; }

            /* Markdown Styling - Harmonized with Frappe */
            .owl-content h1, .owl-content h2, .owl-content h3 { color: var(--text-color); margin: 12px 0 6px; font-weight: 600; }
            .owl-content p { margin-bottom: 8px; }
            .owl-content pre {
                background: var(--code-bg, #f4f4f4);
                padding: 12px;
                border-radius: 8px;
                margin: 12px 0;
                border: 1px solid var(--border-color);
                overflow-x: auto;
            }
            .owl-content code {
                font-family: var(--font-stack-monospace);
                font-size: 0.9em;
                color: var(--primary-color);
                background: var(--bg-light-gray);
                padding: 2px 4px;
                border-radius: 4px;
            }
            .owl-content a { color: var(--primary-color); text-decoration: none; }
            .owl-content a:hover { text-decoration: underline; }

            /* Action Feedback */
            .owl-action-card {
                margin: 8px 0;
                padding: 10px 14px;
                border-radius: 8px;
                background: var(--bg-light-gray);
                border: 1px solid var(--border-color);
                display: flex;
                flex-direction: column;
                gap: 4px;
            }
            .owl-action-card.error {
                border-color: var(--red-200, #fecaca);
                background: var(--red-50, #fef2f2);
            }
            .owl-action-header {
                font-size: 11px;
                font-weight: 700;
                text-transform: uppercase;
                color: #059669;
                display: flex;
                align-items: center;
                gap: 6px;
            }
            .owl-action-header.error {
                color: var(--red-600, #dc2626);
            }
            .owl-action-detail {
                font-size: 12px;
                color: var(--text-muted);
                margin-top: 2px;
            }
        `;
        document.head.appendChild(style);
    }

    bind_shortcuts() {
        frappe.ui.keys.add_shortcut({
            shortcut: 'ctrl+k',
            action: () => this.toggle(),
            description: 'Open OwlAI Assistant'
        });
    }

    mount_navbar_trigger() {
        $(document).on('toolbar_setup', () => {
            const $navbar = $('.navbar .navbar-right .nav.navbar-nav');
            if ($navbar.length && !$('#owl-navbar-trigger').length) {
                const triggerHtml = `
                    <li class="nav-item" id="owl-navbar-trigger" title="OwlAI Assistant (Ctrl+K)">
                        <a class="nav-link" href="#">
                            <svg class="owl-trigger-icon-svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <circle cx="12" cy="12" r="10"></circle>
                                <path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"></path>
                                <path d="M2 12h20"></path>
                            </svg>
                        </a>
                    </li>
                `;
                $(triggerHtml).prependTo($navbar).on('click', (e) => {
                    e.preventDefault();
                    this.toggle();
                });
            }
        });
    }

    create_widget() {
        if (document.getElementById(this.mount_point_id)) return;

        const wrapper = document.createElement('div');
        wrapper.id = this.mount_point_id;

        wrapper.innerHTML = `
            <div id="owl-spotlight-modal">
                <div class="owl-spotlight-glow"></div>
                <div class="owl-bar">
                    <span class="owl-search-icon">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <circle cx="11" cy="11" r="8"></circle>
                            <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                        </svg>
                    </span>
                    <input type="text" id="owl-input" class="owl-input" placeholder="Ask OwlAI anything..." autocomplete="off">
                    <div class="owl-header-actions">
                        <button class="owl-action-btn" id="owl-btn-expand" title="Open Full Chat">
                             <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>
                        </button>
                        <button class="owl-action-btn" id="owl-btn-minimize" title="Minimize">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"></line></svg>
                        </button>
                        <button class="owl-action-btn" id="owl-btn-close" title="Close (Esc)">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                        </button>
                    </div>
                </div>
                <div id="owl-content" class="owl-content">
                    <div class="owl-message system">
                        Assistant ready. Type your command.
                    </div>
                </div>
            </div>
            <div style="position:absolute; width:100%; height:100%; top:0; left:0; z-index:-2" id="owl-backdrop"></div>
        `;

        document.body.appendChild(wrapper);

        document.getElementById('owl-input').addEventListener('keydown', (e) => this.handle_input(e));
        document.getElementById('owl-btn-close').addEventListener('click', () => this.toggle(false));
        document.getElementById('owl-btn-minimize').addEventListener('click', () => this.minimize());
        document.getElementById('owl-backdrop').addEventListener('click', () => this.toggle(false));
        document.getElementById('owl-btn-expand').addEventListener('click', () => {
            window.open('/owlnest/#/chat', '_blank');
        });
    }

    toggle(forceState) {
        this.create_widget();
        const wrapper = document.getElementById(this.mount_point_id);
        const input = document.getElementById('owl-input');

        const nextState = typeof forceState !== 'undefined' ? forceState : !this.is_open;

        if (this.is_minimized && nextState) {
            this.maximize();
            return;
        }

        this.is_open = nextState;

        if (!this.is_open) {
            this.is_minimized = false;
        }

        if (this.is_open) {
            wrapper.classList.remove('hidden');
            setTimeout(() => {
                wrapper.classList.add('active');
                if (!this.is_minimized) input.focus();
            }, 10);
        } else {
            wrapper.classList.remove('active', 'minimized');
            setTimeout(() => {
                if (!this.is_open) wrapper.classList.add('hidden');
            }, 300);
        }
    }

    minimize() {
        const wrapper = document.getElementById(this.mount_point_id);
        if (wrapper && this.is_open) {
            this.is_minimized = true;
            wrapper.classList.add('minimized');
        }
    }

    maximize() {
        const wrapper = document.getElementById(this.mount_point_id);
        const input = document.getElementById('owl-input');
        if (wrapper && this.is_open) {
            this.is_minimized = false;
            wrapper.classList.remove('minimized');
            setTimeout(() => input.focus(), 200);
        }
    }

    async handle_input(e) {
        if (e.key === 'Esc' || e.keyCode === 27) {
            this.toggle(false);
            return;
        }

        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            const input = document.getElementById('owl-input');
            const text = input.value.trim();
            if (!text) return;

            input.value = '';
            this.append_message('user', text);
            await this.stream_response(text);
        }
    }

    append_message(role, content, message_type = 'text', meta = {}) {
        const container = document.getElementById('owl-content');
        const msgDiv = document.createElement('div');
        msgDiv.className = `owl-message ${role}`;

        if (message_type === 'action') {
            const detail = meta.detail || '';
            msgDiv.innerHTML = `
                <div class="owl-action-card">
                    <div class="owl-action-header">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
                        ${content}
                    </div>
                    ${detail ? `<div class="owl-action-detail">${detail}</div>` : ''}
                </div>
            `;
        } else if (message_type === 'error') {
            msgDiv.innerHTML = `
                <div class="owl-action-card error">
                    <div class="owl-action-header error">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>
                        Error
                    </div>
                    <div class="owl-action-detail">${content}</div>
                </div>
            `;
        } else {
            let htmlContent = content;
            if (role !== 'user' && role !== 'system') {
                htmlContent = content.replace(/<thought>[\s\S]*?<\/thought>/g, '').trim();
                if (this.markdown_loaded && typeof marked !== 'undefined' && htmlContent) {
                    htmlContent = marked.parse(htmlContent);
                }
            } else if (role === 'user') {
                htmlContent = frappe.utils.xss_clean ? frappe.utils.xss_clean(htmlContent) : htmlContent;
            }
            msgDiv.innerHTML = htmlContent || "...";
        }

        container.appendChild(msgDiv);
        container.scrollTop = container.scrollHeight;
        return msgDiv;
    }

    _should_start_new_conversation() {
        // Smart conversation continuity based on route context
        const currentRoute = frappe.get_route_str();
        if (!this.conversation_id) return true;
        if (!this._last_route) return false;

        // Extract doctype from routes like "Form/Employee/EMP-001" or "List/Employee"
        const getDoctype = (route) => {
            const parts = (route || '').split('/');
            if (parts[0] === 'Form' || parts[0] === 'List') return parts[1];
            return parts[0];
        };

        const lastDt = getDoctype(this._last_route);
        const currentDt = getDoctype(currentRoute);

        // Same DocType context — continue conversation
        if (lastDt === currentDt) return false;

        // Different DocType — start new conversation
        return true;
    }

    async stream_response(text) {
        const contentDiv = document.getElementById('owl-content');
        const msgDiv = this.append_message('assistant', '');

        const loadingDiv = document.createElement('div');
        loadingDiv.className = 'owl-typing-indicator';
        loadingDiv.innerHTML = '<div class="owl-dot"></div><div class="owl-dot"></div><div class="owl-dot"></div>';
        contentDiv.appendChild(loadingDiv);
        contentDiv.scrollTop = contentDiv.scrollHeight;

        // Smart conversation continuity — new conversation if DocType context changed
        if (this._should_start_new_conversation()) {
            this.conversation_id = null;
            sessionStorage.removeItem('owlai_conversation_id');
            // Clear chat history for new context
            const messages = contentDiv.querySelectorAll('.owl-message:not(.system)');
            messages.forEach(m => m.remove());
        }

        try {
            const currentRoute = frappe.get_route_str();
            const context = {
                route: currentRoute,
                doctype: window.cur_frm ? window.cur_frm.doctype : null,
                docname: window.cur_frm ? window.cur_frm.docname : null,
                form_data: window.cur_frm ? window.cur_frm.doc : null,
                selected_items: window.cur_list ? window.cur_list.get_checked_items(true) : []
            };

            // Track route for conversation continuity
            this._last_route = currentRoute;
            sessionStorage.setItem('owlai_last_route', currentRoute);

            const response = await fetch('/api/method/tb_owlai_core.api.router.handle_stream_input', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Frappe-CSRF-Token': frappe.csrf_token
                },
                body: JSON.stringify({
                    text: text,
                    conversation_id: this.conversation_id,
                    route: currentRoute,
                    context: JSON.stringify(context)
                })
            });

            if (!response.ok) throw new Error("Connection failed");

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            loadingDiv.remove();

            let buffer = "";
            let fullText = "";

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n\n');
                buffer = lines.pop();

                for (const line of lines) {
                    // Handle error events from SSE
                    if (line.trim().startsWith('event: error')) continue;

                    if (line.trim().startsWith('data: ')) {
                        const dataStr = line.replace('data: ', '').trim();
                        if (dataStr === '[DONE]') break;

                        try {
                            const data = JSON.parse(dataStr);
                            if (data.conversation_id) {
                                this.conversation_id = data.conversation_id;
                                sessionStorage.setItem('owlai_conversation_id', data.conversation_id);
                            }

                            if (data.action_data) {
                                (Array.isArray(data.action_data) ? data.action_data : [data.action_data]).forEach(action => {
                                    const params = action.parameters || {};
                                    const actionLabel = action.name.charAt(0).toUpperCase() + action.name.slice(1);
                                    let detail = '';
                                    if (action.name === 'navigate' && params.doctype) {
                                        detail = params.docname
                                            ? `Opening ${params.doctype}: ${params.docname}`
                                            : `Opening ${params.doctype} ${params.view || 'List'}`;
                                    } else if (params.message) {
                                        detail = params.message;
                                    }
                                    this.append_message('assistant', actionLabel, 'action', { detail });
                                    this.handle_action(action);
                                });
                            }

                            if (data.token) {
                                fullText += data.token;
                                let displayUpdate = fullText
                                    .replace(/<thought>[\s\S]*?<\/thought>/g, '')
                                    .replace(/\{"name":\s*"[\w_]+",\s*"parameters":\s*\{[\s\S]*?\}\}/g, '')
                                    .trim();

                                if (this.markdown_loaded && typeof marked !== 'undefined' && displayUpdate) {
                                    msgDiv.innerHTML = marked.parse(displayUpdate);
                                } else {
                                    msgDiv.textContent = displayUpdate || "...";
                                }
                                contentDiv.scrollTop = contentDiv.scrollHeight;
                            }
                        } catch (e) { }
                    }
                }
            }
        } catch (error) {
            loadingDiv.remove();
            this.append_message('system', error.message, 'error');
        }
    }

    handle_action(action) {
        if (action.name === 'navigate') {
            const params = action.parameters || {};
            if (params.doctype) {
                const docname = params.docname || (params.filters && (params.filters.name || params.filters.id));
                const view = params.view || 'List';

                if (docname && view === 'Form') {
                    frappe.set_route('Form', params.doctype, docname);
                } else {
                    if (params.filters) frappe.route_options = params.filters;

                    if (view === 'Page') frappe.set_route(params.doctype);
                    else if (view === 'List') frappe.set_route('List', params.doctype);
                    else if (view === 'Report') frappe.set_route('query-report', params.doctype);
                    else if (view === 'Dashboard') frappe.set_route('dashboard-view', params.doctype);
                    else frappe.set_route('List', params.doctype);
                }
                // Minimize to show the navigation result while keeping AI available
                this.minimize();
            }
        }
    }
}

window.owl_mount = new OwlMount();
