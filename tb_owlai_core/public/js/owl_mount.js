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
            await frappe.require("https://cdn.jsdelivr.net/npm/marked@14.0.0/marked.min.js");
            this.markdown_loaded = true;
        } catch (e) {
            console.warn("OwlAI: Could not load marked.js", e);
        }
    }

    _sanitize_html(html) {
        // Strip dangerous tags/attributes from LLM output before innerHTML
        const div = document.createElement('div');
        div.innerHTML = html;
        // Remove script, iframe, object, embed, form tags
        const dangerous = div.querySelectorAll('script, iframe, object, embed, form, link, meta, base');
        dangerous.forEach(el => el.remove());
        // Remove event handlers from all elements
        div.querySelectorAll('*').forEach(el => {
            for (const attr of [...el.attributes]) {
                if (attr.name.startsWith('on') || attr.name === 'srcdoc' ||
                    (attr.name === 'href' && attr.value.trim().toLowerCase().startsWith('javascript:')) ||
                    (attr.name === 'src' && attr.value.trim().toLowerCase().startsWith('javascript:'))) {
                    el.removeAttribute(attr.name);
                }
            }
        });
        return div.innerHTML;
    }

    init() {
        this.inject_styles();
        this.bind_shortcuts();
        this.mount_navbar_trigger();
        this._bind_realtime_listeners();
    }

    _bind_realtime_listeners() {
        // Listen for setup/initialization progress from backend
        frappe.realtime.on('owlai_setup_progress', (data) => {
            const step = data.step || 'Initializing OwlAI...';
            this._show_setup_banner(step);
        });

        // Listen for model download progress bar
        frappe.realtime.on('progress', (data) => {
            if (data.title === 'OwlAI Model Download') {
                this._show_download_progress(data.percent || 0, data.description || '');
            }
        });
    }

    _show_setup_banner(message) {
        let banner = document.getElementById('owl-setup-banner');
        if (!banner) {
            banner = document.createElement('div');
            banner.id = 'owl-setup-banner';
            banner.className = 'owl-setup-banner';
            document.body.appendChild(banner);
        }
        banner.innerHTML = `
            <div class="owl-setup-icon">&#x1F989;</div>
            <div class="owl-setup-text">
                <span class="owl-setup-label">OwlAI</span>
                <span class="owl-setup-msg">${message}</span>
            </div>
            <div class="owl-setup-spinner"></div>
        `;
        banner.style.display = 'flex';

        // Auto-hide after 30s if no new updates
        clearTimeout(this._setupBannerTimeout);
        this._setupBannerTimeout = setTimeout(() => {
            if (banner) banner.style.display = 'none';
        }, 30000);
    }

    _show_download_progress(percent, description) {
        let banner = document.getElementById('owl-setup-banner');
        if (!banner) {
            this._show_setup_banner(description || 'Downloading model...');
            banner = document.getElementById('owl-setup-banner');
        }

        // Update or create progress bar
        let bar = banner.querySelector('.owl-setup-progress');
        if (!bar) {
            bar = document.createElement('div');
            bar.className = 'owl-setup-progress';
            bar.innerHTML = '<div class="owl-setup-progress-fill"></div>';
            banner.appendChild(bar);
        }
        bar.querySelector('.owl-setup-progress-fill').style.width = percent + '%';

        // Update message
        const msgEl = banner.querySelector('.owl-setup-msg');
        if (msgEl) msgEl.textContent = description || `Downloading model... ${percent}%`;

        // Hide when complete
        if (percent >= 100) {
            setTimeout(() => {
                if (banner) banner.style.display = 'none';
            }, 2000);
        }

        // Extend auto-hide timeout during active download
        clearTimeout(this._setupBannerTimeout);
        this._setupBannerTimeout = setTimeout(() => {
            if (banner) banner.style.display = 'none';
        }, 60000);
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

            /* Progress Steps */
            .owl-progress-step {
                display: flex;
                align-items: center;
                gap: 8px;
                padding: 6px 20px;
                font-size: 12px;
                color: var(--text-muted);
                border-bottom: 1px solid var(--border-color);
                animation: owlFadeIn 0.2s ease both;
            }
            .owl-progress-icon {
                font-size: 14px;
                line-height: 1;
                flex-shrink: 0;
            }
            .owl-progress-icon.done { color: #059669; }
            .owl-progress-icon.error { color: var(--red-600, #dc2626); }
            .owl-progress-icon.pending { color: var(--primary-color); }
            .owl-progress-text { flex: 1; }

            /* Disambiguation Cards */
            .owl-disambiguation-container {
                padding: 10px 20px;
                border-bottom: 1px solid var(--border-color);
                background: var(--bg-color);
                animation: owlFadeIn 0.2s ease both;
            }
            .owl-disambiguation-label {
                font-size: 12px;
                color: var(--text-muted);
                margin-bottom: 8px;
            }
            .owl-disambiguation-cards {
                display: flex;
                flex-wrap: wrap;
                gap: 8px;
            }
            .owl-disambiguation-card {
                padding: 8px 14px;
                border-radius: 8px;
                border: 1px solid var(--border-color);
                background: var(--card-bg, #fff);
                cursor: pointer;
                font-size: 13px;
                color: var(--text-color);
                transition: border-color 0.15s, background 0.15s;
                display: flex;
                flex-direction: column;
                gap: 2px;
                text-align: left;
            }
            .owl-disambiguation-card:hover {
                border-color: var(--primary-color);
                background: var(--bg-light-gray);
            }
            .owl-disambiguation-type {
                font-size: 11px;
                color: var(--text-muted);
                text-transform: uppercase;
                letter-spacing: 0.04em;
            }
            .owl-disambiguation-name {
                font-weight: 500;
            }
            /* Entity action buttons */
            .owl-entity-group {
                margin-bottom: 10px;
            }
            .owl-entity-header {
                font-size: 12px;
                font-weight: 600;
                color: var(--text-color);
                margin-bottom: 4px;
            }
            .owl-entity-actions {
                display: flex;
                flex-wrap: wrap;
                gap: 6px;
            }
            .owl-entity-action-btn {
                padding: 4px 10px;
                border-radius: 6px;
                border: 1px solid var(--border-color);
                background: var(--card-bg, #fff);
                cursor: pointer;
                font-size: 12px;
                color: var(--text-color);
                transition: border-color 0.15s, background 0.15s;
            }
            .owl-entity-action-btn:hover {
                border-color: var(--primary-color);
                background: var(--bg-light-gray);
            }
            .owl-entity-action-btn.primary {
                background: var(--primary-color);
                color: #fff;
                border-color: var(--primary-color);
            }
            .owl-entity-action-btn.primary:hover {
                opacity: 0.9;
            }
            /* Intent action buttons */
            .owl-intent-actions {
                display: flex;
                flex-wrap: wrap;
                gap: 6px;
                margin-top: 4px;
            }
            .owl-intent-btn {
                padding: 5px 12px;
                border-radius: 6px;
                border: 1px solid var(--border-color);
                background: var(--card-bg, #fff);
                cursor: pointer;
                font-size: 12px;
                color: var(--text-color);
                transition: border-color 0.15s, background 0.15s;
            }
            .owl-intent-btn:hover {
                border-color: var(--primary-color);
                background: var(--bg-light-gray);
            }

            /* Suggestion Chips */
            .owl-suggestion-chips {
                padding: 8px 20px;
                border-bottom: 1px solid var(--border-color);
                display: flex;
                gap: 8px;
                overflow-x: auto;
                background: var(--bg-color);
                scrollbar-width: none;
            }
            .owl-suggestion-chips::-webkit-scrollbar { display: none; }
            .owl-chip {
                flex-shrink: 0;
                padding: 4px 12px;
                border-radius: 20px;
                border: 1px solid var(--border-color);
                background: var(--card-bg, #fff);
                color: var(--text-muted);
                font-size: 12px;
                cursor: pointer;
                white-space: nowrap;
                transition: border-color 0.15s, color 0.15s, background 0.15s;
            }
            .owl-chip:hover {
                border-color: var(--primary-color);
                color: var(--primary-color);
                background: var(--bg-light-gray);
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
                this._render_suggestion_chips();
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
                    htmlContent = this._sanitize_html(marked.parse(htmlContent));
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

                    // Handle progress events
                    if (line.trim().startsWith('event: progress')) {
                        continue; // The data line follows
                    }

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
                                    if (action.name === 'ui_sequence') {
                                        detail = params.message || `Executing ${(params.steps || []).length} action(s)...`;
                                    } else if (action.name === 'navigate' && params.doctype) {
                                        detail = params.docname
                                            ? `Opening ${params.doctype}: ${params.docname}`
                                            : `Opening ${params.doctype} ${params.view || 'List'}`;
                                    } else if (action.name === 'new_doc' && params.doctype) {
                                        detail = `Creating new ${params.doctype}`;
                                    } else if (action.name === 'set_value') {
                                        detail = `Setting ${params.fieldname || 'field'}`;
                                    } else if (action.name === 'save') {
                                        detail = 'Saving document';
                                    } else if (params.message) {
                                        detail = params.message;
                                    }
                                    this.append_message('assistant', actionLabel, 'action', { detail });
                                    this.handle_action(action);
                                });
                            }

                            if (data.progress) {
                                const progressDiv = this._render_progress_step(data.progress);
                                if (progressDiv) {
                                    contentDiv.insertBefore(progressDiv, msgDiv);
                                    contentDiv.scrollTop = contentDiv.scrollHeight;
                                }
                            }

                            if (data.disambiguation) {
                                const disambigDiv = this._render_disambiguation(data.disambiguation);
                                if (disambigDiv) {
                                    contentDiv.insertBefore(disambigDiv, msgDiv);
                                    contentDiv.scrollTop = contentDiv.scrollHeight;
                                }
                            }

                            if (data.token) {
                                fullText += data.token;
                                let displayUpdate = fullText
                                    .replace(/<thought>[\s\S]*?<\/thought>/g, '')
                                    .replace(/\{"name":\s*"[\w_]+",\s*"parameters":\s*\{[\s\S]*?\}\}/g, '')
                                    .trim();

                                if (this.markdown_loaded && typeof marked !== 'undefined' && displayUpdate) {
                                    msgDiv.innerHTML = this._sanitize_html(marked.parse(displayUpdate));
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

    _render_progress_step(progress) {
        const div = document.createElement('div');
        div.className = 'owl-progress-step';
        const icon = progress.status === 'done' ? '&#10003;' : progress.status === 'error' ? '&#10007;' : '&#8635;';
        const statusClass = progress.status === 'done' ? 'done' : progress.status === 'error' ? 'error' : 'pending';
        div.innerHTML = `<span class="owl-progress-icon ${statusClass}">${icon}</span><span class="owl-progress-text">${progress.message || ''}</span>`;
        return div;
    }

    _render_disambiguation(disambiguation) {
        const div = document.createElement('div');
        div.className = 'owl-disambiguation-container';

        const options = disambiguation.options || [];
        const suggestedActions = disambiguation.suggested_actions || [];
        const message = disambiguation.message || 'Multiple matches found:';

        let html = `<div class="owl-disambiguation-label">${message}</div>`;

        // Render entity options with action buttons
        if (options.length) {
            html += '<div class="owl-disambiguation-cards">';
            for (const option of options) {
                const displayName = option.display_name || option.name;
                html += `<div class="owl-disambiguation-card">
                    <div class="owl-disambig-info">
                        <span class="owl-disambiguation-type">${option.doctype}</span>
                        <span class="owl-disambiguation-name">${displayName}</span>
                    </div>
                    <div class="owl-disambig-actions">
                        <button class="owl-disambig-btn owl-disambig-open" data-doctype="${option.doctype}" data-name="${option.name}" title="Open record">Open</button>
                        <button class="owl-disambig-btn owl-disambig-use" data-doctype="${option.doctype}" data-name="${option.name}" data-display="${displayName}" title="Use in current query">Use</button>
                    </div>
                </div>`;
            }
            html += '</div>';
        }

        // Render suggested actions (for vague queries like just "Employee")
        if (suggestedActions.length) {
            html += '<div class="owl-disambig-suggestions">';
            for (const sa of suggestedActions) {
                html += `<button class="owl-disambig-suggestion" data-action="${sa.action || 'query'}" data-query="${sa.query || ''}" data-doctype="${sa.doctype || ''}">
                    ${sa.label}
                </button>`;
            }
            html += '</div>';
        }

        // "Create new" option if no exact match
        if (options.length === 0 && disambiguation.doctype) {
            html += `<div class="owl-disambig-suggestions">
                <button class="owl-disambig-suggestion" data-action="navigate" data-doctype="${disambiguation.doctype}">View ${disambiguation.doctype} List</button>
                <button class="owl-disambig-suggestion" data-action="new_doc" data-doctype="${disambiguation.doctype}">Create New ${disambiguation.doctype}</button>
            </div>`;
        }

        div.innerHTML = html;

        // Click handlers — Open button
        div.querySelectorAll('.owl-disambig-open').forEach(btn => {
            btn.addEventListener('click', () => {
                frappe.set_route('Form', btn.dataset.doctype, btn.dataset.name);
                this.minimize();
            });
        });

        // Click handlers — Use button
        div.querySelectorAll('.owl-disambig-use').forEach(btn => {
            btn.addEventListener('click', () => {
                const input = document.getElementById('owl-input');
                input.value = `Use ${btn.dataset.doctype}: ${btn.dataset.display}`;
                this.handle_input(new KeyboardEvent('keydown', {key: 'Enter'}));
            });
        });

        // Click handlers — Suggestion buttons
        div.querySelectorAll('.owl-disambig-suggestion').forEach(btn => {
            btn.addEventListener('click', () => {
                const action = btn.dataset.action;
                if (action === 'navigate') {
                    frappe.set_route('List', btn.dataset.doctype);
                    this.minimize();
                } else if (action === 'new_doc') {
                    frappe.new_doc(btn.dataset.doctype);
                    this.minimize();
                } else if (action === 'search') {
                    const input = document.getElementById('owl-input');
                    input.value = btn.dataset.query;
                    input.focus();
                } else {
                    const input = document.getElementById('owl-input');
                    input.value = btn.dataset.query;
                    this.handle_input(new KeyboardEvent('keydown', {key: 'Enter'}));
                }
            });
        });

        return div;
    }

    _hardcoded_chips() {
        return {
            'Employee': [
                {label: 'Leave balance', query: 'What is my leave balance?'},
                {label: 'Expense claims', query: 'Show pending expense claims'},
                {label: 'Attendance', query: 'Show attendance this month'},
            ],
            'Customer': [
                {label: 'Outstanding', query: 'What is the outstanding balance for this customer?'},
                {label: 'Recent invoices', query: 'Show recent sales invoices for this customer'},
                {label: 'Sales summary', query: 'Sales summary for this customer'},
            ],
            'Sales Order': [
                {label: "Today's orders", query: 'How many sales orders today?'},
                {label: 'Pending delivery', query: 'Show sales orders pending delivery'},
                {label: 'Sales summary', query: 'Show sales summary for this month'},
            ],
            'Sales Invoice': [
                {label: "Today's sales", query: 'Show today sales summary'},
                {label: 'Outstanding', query: 'Show total outstanding invoices'},
                {label: 'Top items', query: 'What are top selling items this month?'},
            ],
            'Item': [
                {label: 'Stock balance', query: 'What is the stock balance for this item?'},
                {label: 'Sales history', query: 'Show sales history for this item'},
            ],
            'Supplier': [
                {label: 'Outstanding', query: 'What is outstanding for this supplier?'},
                {label: 'Recent bills', query: 'Show recent purchase invoices from this supplier'},
            ],
        };
    }

    async _get_suggestion_chips() {
        const route = frappe.get_route_str();
        const parts = (route || '').split('/');
        const doctype = parts[1];

        if (!doctype) return [];

        // Check sessionStorage cache first
        const cacheKey = `owlai_chips_${doctype}`;
        const cached = sessionStorage.getItem(cacheKey);
        if (cached) {
            try {
                return JSON.parse(cached);
            } catch (e) { /* ignore parse errors */ }
        }

        // Try backend API
        try {
            const resp = await fetch(
                `/api/method/tb_owlai_core.api.router.get_suggestion_chips?doctype=${encodeURIComponent(doctype)}`,
                {
                    headers: {
                        'X-Frappe-CSRF-Token': frappe.csrf_token
                    }
                }
            );
            if (resp.ok) {
                const data = await resp.json();
                const chips = data.message || [];
                if (chips.length) {
                    sessionStorage.setItem(cacheKey, JSON.stringify(chips));
                    return chips;
                }
            }
        } catch (e) {
            console.warn('OwlAI: Could not fetch suggestion chips from API', e);
        }

        // Fallback 1: hardcoded map
        const hardcoded = this._hardcoded_chips();
        if (hardcoded[doctype]) return hardcoded[doctype];

        // Fallback 2: generic chips
        return [
            {label: 'Show all records', query: `Show all ${doctype}`},
            {label: 'Create new', query: `Create new ${doctype}`},
        ];
    }

    async _render_suggestion_chips() {
        const existingChips = document.querySelector('.owl-suggestion-chips');
        if (existingChips) existingChips.remove();

        const chips = await this._get_suggestion_chips();
        if (!chips.length) return;

        const container = document.createElement('div');
        container.className = 'owl-suggestion-chips';

        for (const chip of chips) {
            const btn = document.createElement('button');
            btn.className = 'owl-chip';
            btn.textContent = chip.label;
            btn.addEventListener('click', () => {
                const input = document.getElementById('owl-input');
                input.value = chip.query;
                this.handle_input(new KeyboardEvent('keydown', {key: 'Enter'}));
            });
            container.appendChild(btn);
        }

        // Insert after the input bar
        const bar = document.querySelector('.owl-bar');
        if (bar) {
            bar.parentNode.insertBefore(container, bar.nextSibling);
        }
    }

    handle_action(action) {
        const params = action.parameters || {};

        if (action.name === 'ui_sequence') {
            // Multi-step UI automation sequence
            const steps = params.steps || [];
            if (steps.length) {
                this._execute_action_sequence(steps);
            }
            return;
        }

        if (action.name === 'navigate') {
            this._execute_navigate(params);
        } else if (action.name === 'new_doc') {
            this._execute_new_doc(params);
        } else if (action.name === 'set_value') {
            this._execute_set_value(params);
        } else if (action.name === 'save') {
            this._execute_save(params);
        } else if (action.name === 'reload') {
            this._execute_reload(params);
        } else if (action.name === 'show_alert') {
            this._execute_show_alert(params);
        }
    }

    _execute_navigate(params) {
        if (!params.doctype) return;
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
        this.minimize();
    }

    _execute_new_doc(params) {
        if (!params.doctype) return;
        frappe.new_doc(params.doctype, params.initial_values || {});
        this.minimize();
    }

    async _execute_set_value(params) {
        if (!params.fieldname || !window.cur_frm) return;
        const field = params.fieldname;
        const value = params.value;

        await cur_frm.set_value(field, value);

        // Visual highlight on the field
        const fieldEl = cur_frm.fields_dict[field];
        if (fieldEl && fieldEl.$wrapper) {
            fieldEl.$wrapper.addClass('owl-field-highlight');
            setTimeout(() => fieldEl.$wrapper.removeClass('owl-field-highlight'), 1500);
        }
    }

    async _execute_save(params) {
        if (!window.cur_frm) return;
        await cur_frm.save();
    }

    async _execute_reload(params) {
        if (!window.cur_frm) return;
        await cur_frm.reload_doc();
    }

    _execute_show_alert(params) {
        frappe.show_alert({
            message: params.message || 'Action completed',
            indicator: params.indicator || 'green',
        }, 5);
    }

    async _execute_action_sequence(steps) {
        const contentDiv = document.querySelector('.owl-content');
        if (!contentDiv) return;

        // Create progress container in chat
        const progressContainer = document.createElement('div');
        progressContainer.className = 'owl-action-sequence';
        contentDiv.appendChild(progressContainer);

        for (let i = 0; i < steps.length; i++) {
            const step = steps[i];
            const stepDiv = document.createElement('div');
            stepDiv.className = 'owl-action-step';

            // Render all steps: completed / current / pending
            progressContainer.innerHTML = '';
            for (let j = 0; j < steps.length; j++) {
                const s = steps[j];
                const sDiv = document.createElement('div');
                sDiv.className = 'owl-action-step';
                const desc = s.description || s.type;
                if (j < i) {
                    sDiv.innerHTML = '<span class="step-icon step-done">&#10003;</span> ' + desc;
                } else if (j === i) {
                    sDiv.innerHTML = '<span class="step-icon step-active">&#9679;</span> ' + desc + '...';
                } else {
                    sDiv.innerHTML = '<span class="step-icon step-pending">&#9675;</span> ' + desc;
                }
                progressContainer.appendChild(sDiv);
            }
            contentDiv.scrollTop = contentDiv.scrollHeight;

            // Execute the step
            try {
                await this._execute_single_step(step);
            } catch (err) {
                // Mark step as failed
                const failDiv = progressContainer.children[i];
                if (failDiv) {
                    failDiv.innerHTML = '<span class="step-icon step-error">&#10007;</span> ' +
                        (step.description || step.type) + ' — ' + (err.message || 'Failed');
                }
                contentDiv.scrollTop = contentDiv.scrollHeight;
                return;
            }

            // Brief pause between steps for visual clarity
            await new Promise(r => setTimeout(r, 500));
        }

        // Mark all done
        progressContainer.innerHTML = '';
        for (const s of steps) {
            const sDiv = document.createElement('div');
            sDiv.className = 'owl-action-step';
            sDiv.innerHTML = '<span class="step-icon step-done">&#10003;</span> ' + (s.description || s.type);
            progressContainer.appendChild(sDiv);
        }
        contentDiv.scrollTop = contentDiv.scrollHeight;
    }

    async _execute_single_step(step) {
        const type = step.type;
        if (type === 'navigate') {
            this._execute_navigate(step);
            // Wait for route change
            await new Promise(r => setTimeout(r, 1000));
        } else if (type === 'new_doc') {
            this._execute_new_doc(step);
            // Wait for form to load
            await new Promise(resolve => {
                const check = setInterval(() => {
                    if (window.cur_frm && cur_frm.doc && cur_frm.doc.__islocal) {
                        clearInterval(check);
                        resolve();
                    }
                }, 200);
                setTimeout(() => { clearInterval(check); resolve(); }, 5000);
            });
        } else if (type === 'set_value') {
            await this._execute_set_value(step);
        } else if (type === 'save') {
            await this._execute_save(step);
        } else if (type === 'reload') {
            await this._execute_reload(step);
        } else if (type === 'show_alert') {
            this._execute_show_alert(step);
        }
    }
}

// CSS for action sequence steps and field highlight
(function() {
    const style = document.createElement('style');
    style.textContent = `
        .owl-action-sequence {
            padding: 8px 12px;
            margin: 8px 0;
            background: var(--subtle-fg, #f8f9fa);
            border-radius: 8px;
            border-left: 3px solid var(--primary, #6366f1);
        }
        .owl-action-step {
            padding: 4px 0;
            font-size: 13px;
            color: var(--text-muted);
        }
        .step-icon { margin-right: 6px; }
        .step-done { color: var(--green-500, #22c55e); }
        .step-active { color: var(--primary, #6366f1); animation: owl-pulse 1s infinite; }
        .step-pending { color: var(--text-light, #adb5bd); }
        .step-error { color: var(--red-500, #ef4444); }
        @keyframes owl-pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }
        .owl-field-highlight {
            animation: owl-highlight 1.5s ease-out;
        }
        @keyframes owl-highlight {
            0% { background-color: rgba(250, 204, 21, 0.4); }
            100% { background-color: transparent; }
        }
        .owl-disambiguation-card {
            display: flex; justify-content: space-between; align-items: center;
            padding: 8px 12px; margin: 4px 0; border-radius: 6px;
            background: var(--card-bg, #fff); border: 1px solid var(--border-color, #e2e8f0);
        }
        .owl-disambig-info { display: flex; flex-direction: column; gap: 2px; }
        .owl-disambig-actions { display: flex; gap: 6px; }
        .owl-disambig-btn {
            padding: 3px 10px; border-radius: 4px; border: 1px solid var(--border-color);
            background: var(--subtle-fg, #f8f9fa); cursor: pointer; font-size: 12px;
        }
        .owl-disambig-btn:hover { background: var(--primary, #6366f1); color: #fff; border-color: var(--primary); }
        .owl-disambig-suggestions { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
        .owl-disambig-suggestion {
            padding: 5px 12px; border-radius: 16px; border: 1px solid var(--border-color);
            background: var(--subtle-fg, #f8f9fa); cursor: pointer; font-size: 12px;
        }
        .owl-disambig-suggestion:hover { background: var(--primary, #6366f1); color: #fff; border-color: var(--primary); }
        .owl-setup-banner {
            position: fixed; bottom: 20px; right: 20px; z-index: 9998;
            display: none; align-items: center; gap: 10px;
            padding: 10px 16px; border-radius: 10px;
            background: var(--card-bg, #fff); border: 1px solid var(--border-color, #e2e8f0);
            box-shadow: 0 4px 12px rgba(0,0,0,0.1); font-size: 13px; max-width: 360px;
        }
        .owl-setup-icon { font-size: 20px; }
        .owl-setup-text { display: flex; flex-direction: column; gap: 2px; flex: 1; }
        .owl-setup-label { font-weight: 600; font-size: 11px; text-transform: uppercase; color: var(--primary, #6366f1); }
        .owl-setup-msg { color: var(--text-muted); font-size: 12px; }
        .owl-setup-spinner {
            width: 16px; height: 16px; border: 2px solid var(--border-color);
            border-top-color: var(--primary, #6366f1); border-radius: 50%;
            animation: owl-spin 0.8s linear infinite;
        }
        @keyframes owl-spin { to { transform: rotate(360deg); } }
        .owl-setup-progress {
            width: 100%; height: 4px; background: var(--border-color, #e2e8f0);
            border-radius: 2px; margin-top: 6px; overflow: hidden;
        }
        .owl-setup-progress-fill {
            height: 100%; background: var(--primary, #6366f1); border-radius: 2px;
            transition: width 0.3s ease;
        }
    `;
    document.head.appendChild(style);
})();

window.owl_mount = new OwlMount();
