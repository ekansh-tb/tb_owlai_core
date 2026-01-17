/**
 * 🦉 OwlAI Global Mount
 * Enhanced "Spotlight Search" Style Interface for Frappe Desk.
 * Inspired by Vite.dev - Featuring Glassmorphism, Glow effects, and smooth Motion.
 */

class OwlMount {
    constructor() {
        this.is_open = false;
        this.mount_point_id = "owl-spotlight-wrapper";
        this.conversation_id = null;
        this.markdown_loaded = false;

        if (typeof frappe !== 'undefined') {
            frappe.run_serially([
                () => this.load_markdown_lib(),
                () => this.init()
            ]);
        }
    }

    async load_markdown_lib() {
        try {
            await frappe.require("https://cdn.jsdelivr.net/npm/marked/marked.min.js");
            this.markdown_loaded = true;
        } catch (e) {
            console.warn("OwlAI: Could not load marked.js", e);
        }
    }

    init() {
        console.log("🦉 OwlAI Spotlight: Ignite!");
        this.inject_styles();
        this.bind_shortcuts();
        this.mount_navbar_trigger();
    }

    inject_styles() {
        if (document.getElementById('owl-spotlight-styles')) return;
        const style = document.createElement('style');
        style.id = 'owl-spotlight-styles';
        style.textContent = `
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

            #owl-spotlight-wrapper {
                position: fixed;
                top: 0; left: 0; width: 100vw; height: 100vh;
                z-index: 999999;
                display: flex;
                align-items: flex-start;
                justify-content: center;
                padding-top: 15vh;
                background: rgba(0, 0, 0, 0.4);
                backdrop-filter: blur(12px) saturate(180%);
                opacity: 0;
                pointer-events: none;
                transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
                font-family: 'Inter', sans-serif;
            }
            #owl-spotlight-wrapper.active {
                opacity: 1;
                pointer-events: auto;
            }
            
            /* The Vite Glow Effect */
            .owl-spotlight-glow {
                position: absolute;
                width: 800px;
                height: 800px;
                background: radial-gradient(circle, rgba(189, 52, 254, 0.1) 0%, rgba(65, 209, 255, 0.05) 30%, rgba(0, 0, 0, 0) 70%);
                top: 0;
                left: 50%;
                transform: translateX(-50%) translateY(-20%);
                pointer-events: none;
                z-index: -1;
                filter: blur(40px);
            }

            #owl-spotlight-modal {
                width: 800px;
                max-width: 90vw;
                max-height: 70vh;
                background: rgba(20, 20, 20, 0.85);
                border: 1px solid rgba(255, 255, 255, 0.08);
                box-shadow: 0 30px 60px rgba(0, 0, 0, 0.6), inset 0 0 0 1px rgba(255, 255, 255, 0.05);
                border-radius: 20px;
                display: flex;
                flex-direction: column;
                overflow: hidden;
                transform: scale(0.92) translateY(20px);
                transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
            }
            #owl-spotlight-wrapper.active #owl-spotlight-modal {
                transform: scale(1) translateY(0);
            }

            .owl-bar {
                display: flex;
                align-items: center;
                padding: 20px 24px;
                border-bottom: 1px solid rgba(255, 255, 255, 0.06);
                background: rgba(255, 255, 255, 0.01);
            }
            .owl-search-icon {
                color: #bd34fe; /* Vite Purple */
                margin-right: 16px;
                filter: drop-shadow(0 0 8px rgba(189, 52, 254, 0.4));
            }
            .owl-input {
                flex: 1;
                background: transparent;
                border: none;
                color: #fff;
                font-size: 20px;
                outline: none;
                font-weight: 400;
                letter-spacing: -0.01em;
            }
            .owl-input::placeholder {
                color: rgba(255, 255, 255, 0.2);
            }

            .owl-header-actions {
                display: flex;
                gap: 8px;
            }
            .owl-action-btn {
                background: rgba(255, 255, 255, 0.04);
                border: 1px solid rgba(255, 255, 255, 0.02);
                color: rgba(255, 255, 255, 0.4);
                width: 32px; height: 32px;
                border-radius: 8px;
                display: flex;
                align-items: center;
                justify-content: center;
                cursor: pointer;
                transition: all 0.2s;
            }
            .owl-action-btn:hover {
                background: rgba(255, 255, 255, 0.1);
                color: #fff;
                transform: scale(1.05);
            }

            .owl-content {
                flex: 1;
                overflow-y: auto;
                min-height: 120px;
                max-height: 55vh;
                display: flex;
                flex-direction: column;
                scroll-behavior: smooth;
                background: rgba(0, 0, 0, 0.1);
            }
            
            .owl-message {
                padding: 24px 32px;
                border-bottom: 1px solid rgba(255, 255, 255, 0.03);
                font-size: 16px;
                line-height: 1.7;
                color: rgba(255, 255, 255, 0.85);
                animation: owlSlideUp 0.5s ease both;
            }
            .owl-message.user {
                background: rgba(189, 52, 254, 0.03);
                color: #fff;
                font-weight: 500;
            }
            .owl-message.assistant {
                background: transparent;
            }
            .owl-message.system {
                color: rgba(255, 255, 255, 0.3);
                font-size: 13px;
                padding: 16px 32px;
                text-align: center;
            }

            .owl-typing-indicator {
                display: flex;
                gap: 6px;
                padding: 24px 32px;
                align-items: center;
            }
            .owl-dot {
                width: 5px; height: 5px;
                background: #bd34fe;
                border-radius: 50%;
                opacity: 0.6;
                animation: owlPulse 1.5s infinite;
            }
            .owl-dot:nth-child(2) { animation-delay: 0.2s; }
            .owl-dot:nth-child(3) { animation-delay: 0.4s; }

            @keyframes owlSlideUp {
                from { opacity: 0; transform: translateY(10px); }
                to { opacity: 1; transform: translateY(0); }
            }
            @keyframes owlPulse {
                0%, 100% { opacity: 0.2; transform: scale(0.8); }
                50% { opacity: 1; transform: scale(1.2); }
            }

            .owl-trigger-icon-svg {
                filter: drop-shadow(0 0 5px rgba(189, 52, 254, 0.4));
                transition: transform 0.3s ease;
            }
            #owl-navbar-trigger:hover .owl-trigger-icon-svg {
                transform: scale(1.2) rotate(15deg);
            }
            
            .hidden { display: none !important; }

            /* Markdown Styling */
            .owl-content h1, .owl-content h2, .owl-content h3 { color: #fff; margin: 16px 0 8px; font-weight: 700; }
            .owl-content h1 { font-size: 1.5em; }
            .owl-content h2 { font-size: 1.3em; }
            .owl-content h3 { font-size: 1.1em; }
            
            .owl-content p { margin-bottom: 12px; }
            
            .owl-content ul, .owl-content ol { 
                margin: 12px 0; 
                padding-left: 20px; 
                color: rgba(255, 255, 255, 0.8);
            }
            .owl-content li { margin-bottom: 6px; }
            
            .owl-content pre {
                background: #000;
                padding: 16px;
                border-radius: 12px;
                margin: 16px 0;
                border: 1px solid rgba(255,255,255,0.08);
                overflow-x: auto;
            }
            .owl-content code {
                font-family: 'JetBrains Mono', 'Fira Code', monospace;
                font-size: 0.85em;
                color: #41d1ff;
                background: rgba(65, 209, 255, 0.1);
                padding: 2px 6px;
                border-radius: 4px;
            }
            .owl-content pre code {
                background: transparent;
                padding: 0;
                color: #e2e8f0;
            }
            
            .owl-content table {
                width: 100%;
                border-collapse: collapse;
                margin: 16px 0;
                font-size: 0.9em;
            }
            .owl-content th, .owl-content td {
                padding: 10px;
                border: 1px solid rgba(255,255,255,0.06);
                text-align: left;
            }
            .owl-content th { background: rgba(255,255,255,0.04); font-weight: 600; }
            
            .owl-content strong { color: #fff; font-weight: 600; }
            .owl-content blockquote {
                border-left: 4px solid #bd34fe;
                padding-left: 16px;
                margin: 16px 0;
                color: rgba(255,255,255,0.6);
                font-style: italic;
            }
            
            .owl-content a { color: #bd34fe; text-decoration: none; border-bottom: 1px solid transparent; transition: border 0.3s; }
            .owl-content a:hover { border-bottom: 1px solid #bd34fe; }
        `;
        document.head.appendChild(style);
    }

    bind_shortcuts() {
        frappe.ui.keys.add_shortcut({
            shortcut: 'ctrl+k',
            action: () => this.toggle(),
            description: 'Open OwlAI Spotlight'
        });
    }

    mount_navbar_trigger() {
        $(document).on('toolbar_setup', () => {
            const $navbar = $('.navbar .navbar-right .nav.navbar-nav');
            if ($navbar.length && !$('#owl-navbar-trigger').length) {
                $(`<li class="nav-item" id="owl-navbar-trigger" title="Open OwlAI (Ctrl+K)">
                    <a class="nav-link" href="#">
                        <svg class="owl-trigger-icon-svg" width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                            <path d="M12 2L4.5 20.29L5.21 21L12 18L18.79 21L19.5 20.29L12 2Z" fill="url(#vite-gradient)" />
                            <defs>
                                <linearGradient id="vite-gradient" x1="4.5" y1="2" x2="19.5" y2="21" gradientUnits="userSpaceOnUse">
                                    <stop stop-color="#bd34fe" />
                                    <stop offset="1" stop-color="#41d1ff" />
                                </linearGradient>
                            </defs>
                        </svg>
                    </a>
                 </li>`)
                    .prependTo($navbar)
                    .on('click', (e) => {
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
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                            <circle cx="11" cy="11" r="8"></circle>
                            <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                        </svg>
                    </span>
                    <input type="text" id="owl-input" class="owl-input" placeholder="What would you like to build today?" autocomplete="off">
                    <div class="owl-header-actions">
                         <button class="owl-action-btn" id="owl-btn-expand" title="Open Dashboard (Ctrl+Shift+O)">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>
                        </button>
                        <button class="owl-action-btn" id="owl-btn-close" title="Dismiss (Esc)">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                        </button>
                    </div>
                </div>
                <div id="owl-content" class="owl-content">
                    <div class="owl-message system">
                        OwlAI Integration Active • Contextualized to ${frappe.get_route_str() || 'Home'}
                    </div>
                </div>
            </div>
            <div style="position:absolute; width:100%; height:100%; top:0; left:0; z-index:-2" id="owl-backdrop"></div>
        `;

        document.body.appendChild(wrapper);

        document.getElementById('owl-input').addEventListener('keydown', (e) => this.handle_input(e));
        document.getElementById('owl-btn-close').addEventListener('click', () => this.toggle(false));
        document.getElementById('owl-backdrop').addEventListener('click', () => this.toggle(false));
        document.getElementById('owl-btn-expand').addEventListener('click', () => {
            // Fix: Open correct route in new tab using hash routing
            window.open('/owlnest/#/chat', '_blank');
        });
    }

    toggle(forceState) {
        this.create_widget();
        const wrapper = document.getElementById(this.mount_point_id);
        const input = document.getElementById('owl-input');

        const nextState = typeof forceState !== 'undefined' ? forceState : !this.is_open;
        this.is_open = nextState;

        if (this.is_open) {
            wrapper.classList.remove('hidden');
            setTimeout(() => {
                wrapper.classList.add('active');
                input.focus();
            }, 10);
        } else {
            wrapper.classList.remove('active');
            setTimeout(() => {
                if (!this.is_open) wrapper.classList.add('hidden');
            }, 400);
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

    append_message(role, content, message_type = 'text') {
        const container = document.getElementById('owl-content');
        const msgDiv = document.createElement('div');
        msgDiv.className = `owl-message ${role}`;

        if (message_type === 'action') {
            msgDiv.innerHTML = `
                <div style="color: #10b981; font-size: 11px; font-weight: bold; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.05em; display: flex; align-items: center; gap: 6px;">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M2 16V6a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v10"></path><path d="M7 20h10"></path><path d="M12 16v4"></path><path d="M15 8H9"></path></svg>
                    Action Dispatched
                </div>
                <div style="font-family: monospace; font-size: 11px; background: rgba(0,0,0,0.3); padding: 8px; border-radius: 8px; border: 1px solid rgba(16, 185, 129, 0.1); color: rgba(16, 185, 129, 0.8);">
                    ${content}
                </div>
            `;
        } else {
            let htmlContent = content;
            if (role !== 'user' && role !== 'system') {
                // Strip thinking tags
                htmlContent = content.replace(/<thought>[\s\S]*?<\/thought>/g, '').trim();

                if (this.markdown_loaded && typeof marked !== 'undefined' && htmlContent) {
                    htmlContent = marked.parse(htmlContent);
                }
            } else if (role === 'user') {
                htmlContent = frappe.utils.xss_clean ? frappe.utils.xss_clean(content) : content;
            }
            msgDiv.innerHTML = htmlContent || "...";
        }

        container.appendChild(msgDiv);
        container.scrollTop = container.scrollHeight;
        return msgDiv;
    }

    async stream_response(text) {
        const contentDiv = document.getElementById('owl-content');
        const msgDiv = this.append_message('assistant', '');

        const loadingDiv = document.createElement('div');
        loadingDiv.className = 'owl-typing-indicator';
        loadingDiv.innerHTML = '<div class="owl-dot"></div><div class="owl-dot"></div><div class="owl-dot"></div>';
        contentDiv.appendChild(loadingDiv);
        contentDiv.scrollTop = contentDiv.scrollHeight;

        try {
            const context = {
                route: frappe.get_route_str(),
                doctype: window.cur_frm ? window.cur_frm.doctype : null,
                docname: window.cur_frm ? window.cur_frm.docname : null,
                form_data: window.cur_frm ? window.cur_frm.doc : null,
                selected_items: window.cur_list ? window.cur_list.get_checked_items(true) : []
            };

            const response = await fetch('/api/method/tb_owlai_core.api.router.handle_stream_input', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Frappe-CSRF-Token': frappe.csrf_token
                },
                body: JSON.stringify({
                    text: text,
                    conversation_id: this.conversation_id,
                    route: frappe.get_route_str(),
                    context: JSON.stringify(context)
                })
            });

            if (!response.ok) throw new Error("Connection failed");

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            loadingDiv.remove();

            let buffer = "";

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                buffer += chunk;

                const lines = buffer.split('\n\n');
                // The last element is either empty (if chunk ended with \n\n) or incomplete
                buffer = lines.pop();

                for (const line of lines) {
                    if (line.trim().startsWith('data: ')) {
                        const dataStr = line.replace('data: ', '').trim();
                        if (dataStr === '[DONE]') break;

                        try {
                            const data = JSON.parse(dataStr);
                            if (data.conversation_id) this.conversation_id = data.conversation_id;

                            if (data.action_data) {
                                (Array.isArray(data.action_data) ? data.action_data : [data.action_data]).forEach(action => {
                                    this.append_message('assistant', action.name + "(" + JSON.stringify(action.parameters) + ")", 'action');
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
                        } catch (e) {
                            console.warn("OwlAI: Failed to parse SSE data", e);
                        }
                    } else if (line.trim().startsWith('event: error')) {
                        // Handle error event if needed, though we now yield friendly errors as text
                    }
                }
            }
        } catch (error) {
            loadingDiv.remove();
            this.append_message('system', 'Error: ' + error.message);
        }
    }

    handle_action(action) {
        // Execute tool action in Desk
        if (action.name === 'navigate') {
            const params = action.parameters || {};
            if (params.doctype) {
                const docname = params.docname || (params.filters && (params.filters.name || params.filters.id));
                const view = params.view || 'List';

                if (docname && view !== 'Page') {
                    frappe.set_route('Form', params.doctype, docname);
                } else {
                    if (params.filters) {
                        // Correct way to pass filters to a list in Frappe
                        frappe.route_options = params.filters;
                    }

                    if (view === 'Page') {
                        // Standard Page Navigation
                        frappe.set_route(params.doctype);
                    } else if (view === 'List') {
                        frappe.set_route('List', params.doctype);
                    } else if (view === 'Report') {
                        frappe.set_route('query-report', params.doctype);
                    } else if (view === 'Dashboard') {
                        frappe.set_route('dashboard-view', params.doctype);
                    } else {
                        // Fallback
                        frappe.set_route('List', params.doctype);
                    }
                }
                this.toggle(false); // Close spotlight on navigation
            }
        }
    }
}

window.owl_mount = new OwlMount();
