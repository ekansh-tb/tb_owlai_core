/**
 * OwlAI Chat - Intelligent Assistant for Frappe
 * Style: Spotlight/Command Bar
 */
window.OwlChat = class OwlChat {
    constructor() {
        this.socket = null;
        this.conversation_id = null;
        this.conversations = [];
        this.is_open = false;

        if (frappe.ui.toolbar) {
            this.setup_ui();
        } else {
            $(document).on('toolbar_setup', () => this.setup_ui());
        }
    }

    setup_ui() {
        // Prevent duplicate init
        if ($('#owl-spotlight-modal').length) return;

        // 1. Add Icon to Navbar (Near Search/Help)
        this.mount_navbar_icon();

        // 2. Spotlight Modal (Default Expanded)
        this.$modal = $(`
            <div id="owl-spotlight-modal" class="owl-spotlight-overlay hidden">
                <div class="owl-spotlight-container expanded">
                    <!-- SIDEBAR (History) -->
                    <div class="owl-sidebar">
                        <div class="owl-sidebar-header">
                            <span class="font-bold">History</span>
                            <button class="owl-btn-icon owl-sidebar-close">✕</button>
                        </div>
                        <div class="owl-history-list">
                            <div class="text-muted text-center p-3">Loading...</div>
                        </div>
                    </div>

                    <!-- MAIN CHAT AREA -->
                    <div class="owl-main-area">
                        <div class="owl-header">
                            <div class="owl-header-left">
                                <span class="owl-logo">🦉</span>
                                <span class="owl-title">OwlAI</span>
                                <span class="owl-session-indicator"></span>
                            </div>
                            <div class="owl-header-right">
                                 <button class="owl-btn-icon owl-new-chat" title="New Chat (Cmd+Shift+K)">+</button>
                                 <button class="owl-btn-icon owl-history" title="History">🕒</button>
                                 <button class="owl-btn-icon owl-expand-btn" title="Expand/Collapse" style="display:none;">⤢</button>
                                 <button class="owl-btn-icon owl-close-btn" title="Close">✕</button>
                            </div>
                        </div>
                        
                        <div class="owl-messages" id="owl-messages">
                            <div class="message system">
                                👋 Hi! I'm OwlAI. Ask me anything.
                            </div>
                        </div>
                        
                        <div class="owl-input-area">
                            <div class="owl-preview-area hidden" id="owl-preview"></div>
                            <div class="owl-input-wrapper">
                                <div class="owl-search-icon">🦉</div>
                                <textarea id="owl-input" placeholder="Ask OwlAI..."></textarea>
                                <div class="owl-input-actions">
                                    <button id="owl-mic-btn" class="owl-btn-icon" title="Voice Input">🎤</button>
                                    <button id="owl-send-btn" class="owl-send-btn">➤</button>
                                </div>
                            </div>
                            <div class="owl-footer-hint hidden">
                                <span><b>Enter</b> to send</span>
                                <span><b>Shift+Enter</b> for new line</span>
                            </div>
                            
                            <!-- Suggestions Dropdown (Inactive) -->
                            <div class="owl-suggestions"></div>
                        </div>
                    </div>
                </div>
            </div>
        `).appendTo('body');

        // Add Styles
        this.add_styles();
        this.bind_events();
    }

    mount_navbar_icon() {
        // Prevent Duplicate
        if ($('.owl-navbar-icon-li').length) return;

        // Try to place it near the search bar (awesome bar)
        // Standard Frappe v13/14/15 places search in .search-bar or .navbar-center
        // We will try to prepend to .navbar-right to be just to the right of the center block.
        const $navbar_right = $('.navbar .navbar-right .nav.navbar-nav');
        
        if (!$navbar_right.length) {
            // Fallback for different themes/versions
             setTimeout(() => this.mount_navbar_icon(), 1000);
             return;
        }

        // Icon Button
        const $li = $(`
            <li class="nav-item owl-navbar-icon-li" title="Ask OwlAI (Ctrl+K)">
                <a class="nav-link" href="#" onclick="return false;" style="display: flex; align-items: center; padding: 12px 10px;">
                    <span style="font-size: 18px; line-height: 1;">🦉</span>
                </a>
            </li>
        `);

        // Prepend to the right-side menu (making it the first item on the right)
        $navbar_right.prepend($li);

        $li.on('click', (e) => {
            e.preventDefault();
            this.toggle();
        });
    }

    add_styles() {
        const css = `
            :root {
                --owl-bg: var(--card-bg, #ffffff);
                --owl-sidebar-bg: var(--control-bg, #f8fafc);
                --owl-border: var(--border-color, #e2e8f0);
                --owl-text: var(--text-color, #1e293b);
                --owl-text-muted: var(--text-muted, #64748b);
                --owl-hover: var(--fg-hover-color, #f1f5f9);
                --owl-primary: var(--primary-color, #6366f1);
                --owl-primary-fg: #ffffff;
                --owl-user-msg-bg: var(--owl-primary);
                --owl-user-msg-text: #ffffff;
                --owl-assistant-msg-bg: var(--control-bg, #eff6ff);
                --owl-assistant-msg-text: var(--text-color, #1e293b);
                --owl-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
                --owl-font: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                --owl-radius: 16px;
                --owl-transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
            }
            [data-theme="dark"] {
                --owl-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.5);
                --owl-assistant-msg-bg: var(--control-bg, #1e293b);
            }

            /* Global Reset for Owl Modal */
            .owl-spotlight-container *, .owl-spotlight-container *::before, .owl-spotlight-container *::after {
                box-sizing: border-box;
            }

            /* Overlay */
            .owl-spotlight-overlay {
                position: fixed;
                top: 0; left: 0; right: 0; bottom: 0;
                background: rgba(0, 0, 0, 0.3);
                backdrop-filter: blur(4px);
                z-index: 10001;
                display: flex;
                align-items: center; 
                justify-content: center;
                opacity: 0;
                pointer-events: none;
                transition: opacity 0.2s ease;
            }
            .owl-spotlight-overlay:not(.hidden) {
                opacity: 1;
                pointer-events: auto;
            }

            /* Container */
            .owl-spotlight-container {
                width: 960px;
                max-width: 95vw;
                height: 750px;
                max-height: 90vh;
                background: var(--owl-bg);
                border-radius: var(--owl-radius);
                box-shadow: var(--owl-shadow);
                display: flex;
                flex-direction: row;
                overflow: hidden;
                transform: scale(0.98) translateY(10px);
                transition: transform 0.2s ease, opacity 0.2s ease;
                border: 1px solid var(--owl-border);
                color: var(--owl-text);
                font-family: var(--owl-font);
            }
            .owl-spotlight-overlay:not(.hidden) .owl-spotlight-container {
                transform: scale(1) translateY(0);
            }

            /* Sidebar */
            .owl-sidebar {
                width: 0;
                background: var(--owl-sidebar-bg);
                border-right: 1px solid var(--owl-border);
                display: flex;
                flex-direction: column;
                transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                overflow: hidden;
            }
            .owl-sidebar.expanded {
                width: 280px;
            }
            .owl-sidebar-header {
                padding: 18px 20px;
                font-weight: 700;
                font-size: 14px;
                letter-spacing: 0.02em;
                border-bottom: 1px solid var(--owl-border);
                display: flex; justify-content: space-between; align-items: center;
                color: var(--owl-text);
                background: var(--owl-sidebar-bg);
            }
            
            .owl-history-list {
                flex: 1;
                overflow-y: auto;
                padding: 12px;
            }
            /* Custom Scrollbar */
            .owl-history-list::-webkit-scrollbar, .owl-messages::-webkit-scrollbar {
                width: 6px;
            }
            .owl-history-list::-webkit-scrollbar-thumb, .owl-messages::-webkit-scrollbar-thumb {
                background: var(--owl-border);
                border-radius: 3px;
            }

            .owl-history-group {
                font-size: 11px;
                font-weight: 700;
                color: var(--owl-text-muted);
                text-transform: uppercase;
                letter-spacing: 0.05em;
                margin: 20px 12px 8px 12px;
            }
            
            .owl-history-item {
                padding: 10px 14px;
                margin-bottom: 4px;
                border-radius: 8px;
                font-size: 13px;
                cursor: pointer;
                color: var(--owl-text);
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
                transition: var(--owl-transition);
                border: 1px solid transparent;
            }
            .owl-history-item:hover {
                background: var(--owl-hover);
                transform: translateX(2px);
            }
            .owl-history-item.active {
                background: var(--owl-bg);
                border-color: var(--owl-border);
                font-weight: 600;
                box-shadow: 0 2px 4px rgba(0,0,0,0.03);
            }

            /* Main Area */
            .owl-main-area {
                flex: 1;
                display: flex;
                flex-direction: column;
                min-width: 0;
                background: var(--owl-bg);
            }

            /* Header */
            .owl-header {
                padding: 16px 24px;
                border-bottom: 1px solid var(--owl-border);
                display: flex; justify-content: space-between; align-items: center;
                background: rgba(255,255,255,0.05); /* Slight transparency helper */
            }
            .owl-header-left { display: flex; align-items: center; gap: 12px; font-weight: 700; font-size: 18px; color: var(--owl-text); }
            .owl-logo { font-size: 24px; filter: drop-shadow(0 2px 4px rgba(0,0,0,0.1)); }
            
            .owl-header-right { display: flex; align-items: center; gap: 8px; }
            .owl-btn-icon {
                background: transparent; border: 1px solid transparent; cursor: pointer; padding: 8px;
                color: var(--owl-text-muted); transition: var(--owl-transition); border-radius: 8px;
                display: inline-flex; align-items: center; justify-content: center;
                height: 34px; width: 34px;
            }
            .owl-btn-icon:hover { 
                background: var(--owl-hover); 
                color: var(--owl-text); 
                border-color: var(--owl-border);
            }

            /* Messages */
            .owl-messages {
                flex: 1;
                padding: 24px;
                overflow-y: auto;
                display: flex;
                flex-direction: column;
                gap: 24px;
                scroll-behavior: smooth;
            }

            .message {
                max-width: 80%;
                padding: 14px 18px;
                border-radius: 18px;
                font-size: 15px;
                line-height: 1.6;
                position: relative;
                word-wrap: break-word;
                animation: fadeIn 0.3s ease-out forwards;
                box-shadow: 0 1px 2px rgba(0,0,0,0.05);
            }
            @keyframes fadeIn {
                from { opacity: 0; transform: translateY(10px); }
                to { opacity: 1; transform: translateY(0); }
            }

            .message.system { 
                align-self: center; 
                background: var(--owl-sidebar-bg); 
                color: var(--owl-text-muted); 
                font-size: 13px; 
                padding: 8px 16px;
                border: 1px solid var(--owl-border);
                border-radius: 24px;
                max-width: 90%;
                text-align: center;
                box-shadow: none;
            }
            .message.user { 
                align-self: flex-end; 
                background: var(--owl-user-msg-bg); 
                color: var(--owl-user-msg-text); 
                border-bottom-right-radius: 4px; 
            }
            /* Assistant Message */
            .message.assistant { 
                align-self: flex-start; 
                background: var(--owl-assistant-msg-bg); 
                color: var(--owl-assistant-msg-text); 
                border-bottom-left-radius: 4px;
                border: 1px solid var(--owl-border);
            }
            /* Formatted Content inside Messages */
            .message-content h1, .message-content h2, .message-content h3 {
                margin-top: 0.5em; margin-bottom: 0.5em; font-weight: 700;
            }
            .message-content p { margin-bottom: 0.5em; }
            .message-content p:last-child { margin-bottom: 0; }
            .message-content pre { 
                background: rgba(0,0,0,0.05); padding: 10px; border-radius: 8px; margin: 8px 0; overflow-x: auto; 
            }
            .message-content code {
                font-family: 'Fira Code', monospace;
                font-size: 0.9em;
            }

            .message-time {
                font-size: 10px;
                margin-top: 6px;
                text-align: right;
                opacity: 0.6;
                display: block;
                font-weight: 500;
            }
            
            /* Input Area */
            .owl-input-area {
                padding: 20px 24px;
                border-top: 1px solid var(--owl-border);
                background: var(--owl-bg);
            }
            .owl-input-wrapper {
                background: var(--owl-sidebar-bg); /* Contrast */
                border: 1px solid var(--owl-border);
                border-radius: 14px;
                padding: 12px 16px;
                display: flex;
                align-items: flex-end;
                transition: var(--owl-transition);
                box-shadow: inset 0 1px 2px rgba(0,0,0,0.03);
            }
            .owl-input-wrapper:focus-within { 
                border-color: var(--owl-primary); 
                box-shadow: 0 0 0 3px var(--primary-light, rgba(99, 102, 241, 0.2)); 
                background: var(--owl-bg);
            }
            
            .owl-search-icon { font-size: 20px; margin-right: 12px; margin-bottom: 4px; opacity: 0.8; }

            #owl-input {
                flex: 1;
                border: none;
                outline: none;
                resize: none;
                max-height: 200px;
                min-height: 24px;
                font-family: inherit;
                font-size: 15px;
                padding: 4px 0;
                background: transparent;
                color: var(--owl-text);
                line-height: 1.5;
            }
            #owl-input::placeholder { color: var(--owl-text-muted); opacity: 0.7; }

            .owl-input-actions { display: flex; align-items: center; gap: 8px; margin-left: 12px; padding-bottom: 2px; }
            .owl-send-btn { 
                background: var(--owl-primary); color: white; 
                width: 36px; height: 36px; 
                border-radius: 10px; border: none; 
                display: flex; align-items: center; justify-content: center;
                cursor: pointer; transition: var(--owl-transition);
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            }
            .owl-send-btn:hover { transform: translateY(-1px); box-shadow: 0 4px 8px rgba(0,0,0,0.15); }
            .owl-send-btn:active { transform: translateY(0); }
            
            .owl-footer-hint {
                display: flex; justify-content: flex-end; gap: 16px;
                font-size: 11px; color: var(--owl-text-muted); margin-top: 10px;
                font-weight: 500;
            }

            /* Config Form */
            .owl-config-form {
                background: var(--owl-bg);
                padding: 16px;
                border-radius: 12px;
                border: 1px solid var(--owl-border);
                margin-top: 12px;
                display: flex; flex-direction: column; gap: 12px;
                box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
            }
            .owl-config-save {
                background: var(--owl-primary); color: white; border: none; padding: 10px; border-radius: 8px;
                cursor: pointer; font-size: 13px; font-weight: 600;
            }

            /* List Results */
            .owl-list-results { display: flex; flex-direction: column; gap: 10px; margin-top: 12px; }
            .owl-list-item { 
                background: var(--owl-bg); 
                border: 1px solid var(--owl-border); 
                padding: 12px 16px; border-radius: 10px; 
                cursor: pointer; transition: all 0.2s;
                color: var(--owl-text);
            }
            .owl-list-item:hover { 
                border-color: var(--owl-primary); 
                box-shadow: 0 4px 12px rgba(0,0,0,0.05); 
                transform: translateY(-2px);
            }
        `;
        $('<style>').text(css).appendTo('head');
    }

    bind_events() {
        // Close on Overlay Click
        this.$modal.on('click', (e) => {
            if ($(e.target).is('.owl-spotlight-overlay')) this.toggle();
        });
        this.$modal.find('.owl-close-btn').on('click', () => this.toggle());

        // Send
        this.$modal.find('#owl-send-btn').on('click', () => this.send_message());
        const $input = this.$modal.find('#owl-input');
        $input.on('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.send_message();
            }
        });

        // Suggestions Input Listener - DISABLED
        // $input.on('input', (e) => this.handle_input_change(e));
        // $input.on('focus', () => { if($input.val().trim()) this.show_suggestions(); });

        // New Chat
        this.$modal.find('.owl-new-chat').on('click', () => this.start_new_conversation());

        // History Sidebar Toggle
        this.$modal.find('.owl-history').on('click', () => this.toggle_sidebar());
        this.$modal.find('.owl-sidebar-close').on('click', () => this.toggle_sidebar(false));

        // Voice
        this.setup_voice();
        // Paste
        this.$modal.find('#owl-input').on('paste', (e) => this.handle_paste(e));
    }

    toggle_sidebar(forceState) {
        const $sidebar = this.$modal.find('.owl-sidebar');
        const currentState = $sidebar.hasClass('expanded');
        const newState = forceState !== undefined ? forceState : !currentState;

        if (newState) {
            $sidebar.addClass('expanded');
            this.show_conversation_history();
        } else {
            $sidebar.removeClass('expanded');
        }
    }

    toggle() {
        this.is_open = !this.is_open;
        if (this.is_open) {
            this.start_new_conversation();
            this.$modal.removeClass('hidden');
            setTimeout(() => this.$modal.find('#owl-input').focus(), 50);

            // Show sidebar by default on large screens
            if (window.innerWidth > 768) {
                this.$modal.find('.owl-sidebar').addClass('expanded'); // Ensure sidebar is expanded
                this.show_conversation_history();
            }
            // Ensure expanded class is set
            this.$modal.find('.owl-spotlight-container').removeClass('compact').addClass('expanded');
        } else {
            this.$modal.addClass('hidden');
        }
    }

    start_new_conversation() {
        this.conversation_id = null;
        localStorage.removeItem('owlai_conversation_id');
        this.$modal.find('#owl-messages').empty();
        this.add_message("Starting a new conversation. How can I help?", 'system');
        this.update_session_indicator();
        this.$modal.find('.owl-history-item').removeClass('active');
    }

    update_session_indicator() {
        const text = this.conversation_id ? `Session: ${this.conversation_id.slice(-5)}` : '';
        this.$modal.find('.owl-session-indicator').text(text).toggle(!!this.conversation_id);
    }

    // ... Copy remaining core logic from previous file (load_last_conversation, show_conversation_history, process_request, etc)
    // But update handle_response for CONFIG

    load_last_conversation() {
        const saved_id = localStorage.getItem('owlai_conversation_id');
        if (saved_id) {
            this.conversation_id = saved_id;
            this.update_session_indicator();
        }
    }

    save_conversation_id(conv_id) {
        if (conv_id) {
            this.conversation_id = conv_id;
            localStorage.setItem('owlai_conversation_id', conv_id);
            this.update_session_indicator();
        }
    }

    show_conversation_history() {
        // Show loading state if empty
        const $list = this.$modal.find('.owl-history-list');
        if ($list.is(':empty')) $list.html('<div class="text-muted small p-2">Loading...</div>');

        frappe.call({
            method: 'tb_owlai_core.api.router.get_conversations',
            args: { limit: 20 },
            callback: (r) => {
                if (r.message) {
                    this.render_conversation_list(r.message);
                }
            }
        });
    }

    render_conversation_list(conversations) {
        const $list = this.$modal.find('.owl-history-list');
        $list.empty();

        if (conversations.length === 0) {
            $list.html('<div class="text-muted small p-2">No history found.</div>');
            return;
        }

        // Grouping Logic
        const today = moment().format('YYYY-MM-DD');
        const yesterday = moment().subtract(1, 'days').format('YYYY-MM-DD');
        const last7Days = moment().subtract(7, 'days');

        const groups = {
            'Today': [],
            'Yesterday': [],
            'Previous 7 Days': [],
            'Older': []
        };

        conversations.forEach(conv => {
            const date = conv.modified.split(" ")[0]; // "2024-01-04"
            if (date === today) groups['Today'].push(conv);
            else if (date === yesterday) groups['Yesterday'].push(conv);
            else if (moment(date).isAfter(last7Days)) groups['Previous 7 Days'].push(conv);
            else groups['Older'].push(conv);
        });

        // Render Groups
        Object.keys(groups).forEach(label => {
            const items = groups[label];
            if (items.length === 0) return;

            $list.append(`<div class="owl-history-group">${label}</div>`);

            items.forEach(conv => {
                // Determine Title: Use conv.title, or if missing/empty, use a friendly "New Chat" with small ID
                let title = conv.title;
                if (!title || title.trim() === '') {
                    title = "Conversation " + conv.name.slice(-4);
                }

                const activeClass = (this.conversation_id === conv.name) ? 'active' : '';

                const $item = $(`
                    <div class="owl-history-item ${activeClass}" data-id="${conv.name}" title="${title}">
                        <div class="owl-history-title">${title}</div>
                    </div>
                `);

                $item.on('click', () => this.load_conversation(conv.name));
                $list.append($item);
            });
        });
    }

    load_conversation(conversation_id) {
        if (this.conversation_id === conversation_id) return;

        this.save_conversation_id(conversation_id);
        this.$modal.find('.owl-history-item').removeClass('active');
        this.$modal.find(`.owl-history-item[data-id="${conversation_id}"]`).addClass('active');

        // Load Messages
        this.$modal.find('#owl-messages').html('<div class="message system">Loading conversation...</div>');

        frappe.call({
            method: 'tb_owlai_core.api.router.get_conversation_messages',
            args: { conversation_id: conversation_id },
            callback: (r) => {
                this.$modal.find('#owl-messages').empty();
                if (r.message && r.message.length) {
                    // Sort by idx (primary) and creation (secondary)
                    r.message.sort((a, b) => {
                        // Use idx if available and distinct
                        if (a.idx !== undefined && b.idx !== undefined && a.idx !== b.idx) {
                            return a.idx - b.idx;
                        }
                        // Fallback to creation time
                        return (a.creation > b.creation) ? 1 : -1;
                    });

                    r.message.forEach(msg => {
                        if (msg.role === 'user') {
                            this.add_message(frappe.markdown(msg.content), 'user', msg.creation);
                        } else if (msg.role === 'assistant') {
                            if (msg.message_type === 'action') {
                                const text = msg.content || "Executed Action";
                                this.add_message(frappe.markdown(text), 'assistant', msg.creation);
                            } else {
                                this.add_message(frappe.markdown(msg.content), 'assistant', msg.creation);
                            }
                        }
                    });
                    const $msgs = this.$modal.find('#owl-messages');
                    $msgs.scrollTop($msgs[0].scrollHeight);
                } else {
                    this.add_message("Conversation loaded (empty logs).", 'system');
                }
            }
        });
    }

    // === Messaging ===

    add_message(html, role, timestamp = null) {
        const $msgs = this.$modal.find('#owl-messages');
        const timeStr = timestamp ? frappe.datetime.str_to_user(timestamp).split(" ")[1] : moment().format('HH:mm');
        const displayTime = timeStr.slice(0, 5); // 14:30

        const msgHtml = `
            <div class="message ${role}">
                <div class="message-content">${html}</div>
                ${role !== 'system' ? `<span class="message-time">${displayTime}</span>` : ''}
            </div>
        `;

        $(msgHtml).appendTo($msgs);

        // Auto scroll if needed
        $msgs.scrollTop($msgs[0].scrollHeight);
    }

    send_message() {
        const $input = this.$modal.find('#owl-input');
        const text = $input.val().trim();
        if (!text && !this.current_attachment) return;

        if (text) this.add_message(text, 'user');
        if (this.current_attachment) {
            const url = URL.createObjectURL(this.current_attachment);
            this.add_message(`<img src="${url}">`, 'user');
        }

        this.process_request(text, this.current_attachment);
        $input.val('');
        this.current_attachment = null;
        this.$modal.find('#owl-preview').addClass('hidden').empty();
    }

    process_request(text, imageFile, audioBlob) {
        this.add_message('Thinking...', 'assistant loading');

        // Context Gathering
        let context = {};
        try {
            context = {
                route: frappe.get_route_str(),
                form_data: (window.cur_frm && window.cur_frm.doc) ? window.cur_frm.doc : {},
                selected_items: (window.cur_list && window.cur_list.get_checked_items) ? window.cur_list.get_checked_items(true) : []
            };
        } catch (e) {
            console.warn("OwlAI: Failed to gather context", e);
        }

        const formData = new FormData();
        if (text) formData.append('text', text);
        if (imageFile) formData.append('image', imageFile);
        if (audioBlob) formData.append('audio', audioBlob, 'voice.wav');
        formData.append('route', frappe.get_route_str());
        formData.append('context', JSON.stringify(context));

        if (this.conversation_id) formData.append('conversation_id', this.conversation_id);

        fetch('/api/method/tb_owlai_core.api.router.handle_input_v2', {
            method: 'POST',
            headers: { 'X-Frappe-CSRF-Token': frappe.csrf_token },
            body: formData
        })
            .then(r => r.json())
            .then(res => this.handle_response(res))
            .catch(err => {
                this.remove_loading();
                this.add_message("Error: " + err, 'assistant');
            });
    }

    handle_response(res) {
        this.remove_loading();
        if (res.exc) { console.error(res.exc); this.add_message("Error occurred.", 'assistant'); return; }

        const data = res.message;
        if (!data) return;

        if (data.conversation_id) {
            const is_new = this.conversation_id !== data.conversation_id;
            this.save_conversation_id(data.conversation_id);
            if (is_new) this.show_conversation_history();
        }

        // CONFIG NEEDED?
        if (data.config_needed) {
            this.render_config_form(data);
            return;
        }

        // TEXT
        if (data.reply) {
            this.add_message(frappe.markdown(data.reply), 'assistant');
        }

        // ACTIONS
        if (data.action) this.handle_action(data);
    }

    render_config_form(data) {
        const modelOptions = data.models.map(m => `<option value="${m}" ${m.includes(data.current_model) ? 'selected' : ''}>${m}</option>`).join('');
        const apiKeyField = data.ask_api_key ? `
            <label>API Key Required</label>
            <input type="password" class="owl-api-key" placeholder="Enter Gemini API Key">
        ` : '';

        const html = `
            <div>
                <p>${frappe.markdown(data.reply)}</p>
                <div class="owl-config-form">
                    <label>Select Model</label>
                    <select class="owl-model-select">${modelOptions}</select>
                    ${apiKeyField}
                    <button class="owl-config-save">Save & Retry</button>
                </div>
            </div>
        `;

        this.add_message(html, 'assistant');

        // Bind Save
        const $lastMsg = this.$modal.find('.message.assistant').last();
        $lastMsg.find('.owl-config-save').on('click', () => {
            const model = $lastMsg.find('.owl-model-select').val();
            const key = $lastMsg.find('.owl-api-key').val();

            frappe.call({
                method: 'tb_owlai_core.api.router.update_owlai_settings',
                args: { model: model, api_key: key },
                callback: (r) => {
                    if (r.message && r.message.status === 'success') {
                        frappe.show_alert('Settings Updated!', 5);
                        this.add_message("✅ Settings saved. Please try your request again.", 'system');
                    }
                }
            });
        });
    }

    handle_action(data) {
        if (data.action === 'create_doc') {
            frappe.model.with_doctype(data.doctype, () => {
                let doc = frappe.model.get_new_doc(data.doctype);
                Object.assign(doc, data.data);
                frappe.set_route('Form', data.doctype, doc.name);
                this.add_message(`Drafted ${data.doctype}...`, 'assistant');
                this.toggle(); // Close chat to show user
            });
        } else if (data.action === 'navigate') {
            if (data.route_options) {
                frappe.route_options = data.route_options;
            }

            if (data.name) {
                frappe.set_route(data.view || 'Form', data.doctype, data.name);
            } else {
                frappe.set_route(data.view || 'List', data.doctype);
            }

            this.toggle();
        } else if (data.action === 'reload') {
            frappe.ui.toolbar.clear_cache();
            frappe.router.reload();
            this.toggle();
        } else if (data.action === 'list') {
            // Render a mini list in the chat
            let html = `<div class="owl-list-results">`;
            if (Array.isArray(data.data) && data.data.length > 0) {
                data.data.forEach(item => {
                    html += `
                        <div class="owl-list-item" onclick="frappe.set_route('Form', '${data.doctype}', '${item.name}')">
                            <div class="font-bold">${item.title || item.name}</div>
                            <div class="text-muted small">${item.status || ''} · ${frappe.datetime.prettyDate(item.modified)}</div>
                        </div>
                    `;
                });
            } else {
                html += `<div class="text-muted">No results found.</div>`;
            }
            html += `</div>`;

            // Add style on the fly if needed (or assume it inherits from general styles)
            this.add_message(html, 'assistant');
        }
    }

    remove_loading() { this.$modal.find('.message.loading').remove(); }

    // Voice & File handlers (simplified)
    setup_voice() {
        const $mic = this.$modal.find('#owl-mic-btn');
        $mic.on('click', () => {
            frappe.msgprint("Voice integration paused for update. Please type for now!");
        });
    }

    handle_paste(e) {
        const items = (e.originalEvent || e).clipboardData.items;
        for (let item of items) {
            if (item.kind === 'file' && item.type.includes('image')) {
                this.current_attachment = item.getAsFile();
                const url = URL.createObjectURL(this.current_attachment);
                this.$modal.find('#owl-preview').removeClass('hidden')
                    .html(`<img src="${url}" class="owl-preview-img">`);
            }
        }
    }
}
