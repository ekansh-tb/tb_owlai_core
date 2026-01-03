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
        
        // Wait for Frappe Navbar to be ready
        if (frappe.ui.toolbar) {
             this.setup_ui();
        } else {
             $(document).on('toolbar_setup', () => this.setup_ui());
        }
        
        this.load_last_conversation();
    }

    setup_ui() {
        // Prevent duplicate init
        if ($('#owl-spotlight-modal').length) return;

        // 1. Add Icon to Navbar (Near Search/Help)
        this.mount_navbar_icon();

        // 2. Spotlight Modal
        this.$modal = $(`
            <div id="owl-spotlight-modal" class="owl-spotlight-overlay hidden">
                <div class="owl-spotlight-container">
                    <div class="owl-header">
                        <div class="owl-header-left">
                            <span class="owl-logo">🦉</span>
                            <span class="owl-title">OwlAI</span>
                            <span class="owl-session-indicator"></span>
                        </div>
                        <div class="owl-header-right">
                             <button class="owl-btn-icon owl-new-chat" title="New Chat (Cmd+Shift+K)">+</button>
                             <button class="owl-btn-icon owl-history" title="History">🕒</button>
                             <button class="owl-btn-icon owl-close-btn" title="Close">✕</button>
                        </div>
                    </div>
                    
                    <div class="owl-messages" id="owl-messages">
                        <div class="message system">
                            👋 Hi! I'm OwlAI. Press <b>/</b> to see commands or just ask me anything.
                        </div>
                    </div>
                    
                    <div class="owl-input-area">
                        <div class="owl-preview-area hidden" id="owl-preview"></div>
                        <div class="owl-input-wrapper">
                            <textarea id="owl-input" placeholder="Ask OwlAI..."></textarea>
                            <div class="owl-input-actions">
                                <button id="owl-mic-btn" class="owl-btn-icon" title="Voice Input">🎤</button>
                                <button id="owl-send-btn" class="owl-send-btn">➤</button>
                            </div>
                        </div>
                        <div class="owl-footer-hint">
                            <span><b>Enter</b> to send</span>
                            <span><b>Shift+Enter</b> for new line</span>
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
        // Find the navbar actions area
        const $navbar_right = $('.navbar .navbar-right .nav.navbar-nav');
        
        // Insert before Help or User menu
        const $li = $(`
            <li class="dropdown">
                <a class="nav-link text-muted owl-navbar-icon" href="#" onclick="return false;" title="OwlAI Assistant (Shift+Ctrl+L)">
                    <span>🦉</span>
                </a>
            </li>
        `);
        
        $navbar_right.prepend($li);
        
        $li.on('click', (e) => {
            e.preventDefault();
            this.toggle();
        });
    }

    add_styles() {
        const css = `
            /* Overlay */
            .owl-spotlight-overlay {
                position: fixed;
                top: 0; left: 0; right: 0; bottom: 0;
                background: rgba(0,0,0,0.4);
                backdrop-filter: blur(2px);
                z-index: 10001;
                display: flex;
                align-items: flex-start; /* Top aligned like Spotlight */
                justify-content: center;
                padding-top: 8vh;
                opacity: 0;
                pointer-events: none;
                transition: opacity 0.2s;
            }
            .owl-spotlight-overlay:not(.hidden) {
                opacity: 1;
                pointer-events: auto;
            }

            /* Container */
            .owl-spotlight-container {
                width: 700px;
                max-width: 90vw;
                height: 600px;
                max-height: 80vh;
                background: var(--card-bg, #fff);
                border-radius: 12px;
                box-shadow: 0 20px 50px rgba(0,0,0,0.25);
                display: flex;
                flex-direction: column;
                overflow: hidden;
                transform: translateY(20px);
                transition: transform 0.2s;
                border: 1px solid var(--border-color, #e2e8f0);
            }
            .owl-spotlight-overlay:not(.hidden) .owl-spotlight-container {
                transform: translateY(0);
            }

            /* Header */
            .owl-header {
                padding: 12px 20px;
                border-bottom: 1px solid var(--border-color, #eee);
                display: flex;
                justify-content: space-between;
                background: var(--bg-light-gray, #fcfcfc);
            }
            .owl-header-left { display: flex; align-items: center; gap: 10px; font-weight: 600; font-size: 16px; }
            .owl-logo { font-size: 20px; }
            .owl-session-indicator { font-size: 11px; background: #eef2ff; color: #4338ca; padding: 2px 8px; border-radius: 12px; font-weight: normal; }
            .owl-header-right { display: flex; gap: 5px; }
            .owl-close-btn { font-size: 18px; width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; border-radius: 4px; }
            .owl-close-btn:hover { background: #fee2e2; color: #dc2626; }

            /* Messages */
            .owl-messages {
                flex: 1;
                padding: 20px;
                overflow-y: auto;
                display: flex;
                flex-direction: column;
                gap: 16px;
                background: var(--card-bg, #fff);
            }

            .message {
                max-width: 85%;
                padding: 12px 16px;
                border-radius: 12px;
                font-size: 15px;
                line-height: 1.6;
            }
            .message.system { align-self: center; background: #f8fafc; color: #64748b; font-size: 13px; text-align: center; border: 1px solid #e2e8f0; }
            .message.user { align-self: flex-end; background: #4f46e5; color: white; border-bottom-right-radius: 2px; }
            .message.assistant { align-self: flex-start; background: #f1f5f9; color: #1e293b; border-bottom-left-radius: 2px; }
            .message img { max-width: 100%; border-radius: 8px; margin-top: 5px; }
            
            /* Input Area */
            .owl-input-area {
                padding: 16px 20px;
                border-top: 1px solid var(--border-color, #eee);
                background: #fcfcfc;
            }
            .owl-input-wrapper {
                background: white;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 8px 12px;
                display: flex;
                align-items: flex-end;
                box-shadow: 0 2px 4px rgba(0,0,0,0.02);
            }
            .owl-input-wrapper:focus-within { border-color: #6366f1; ring: 2px solid #e0e7ff; }
            
            #owl-input {
                flex: 1;
                border: none;
                outline: none;
                resize: none;
                max-height: 120px;
                min-height: 24px;
                font-family: inherit;
                font-size: 15px;
                padding: 4px 0;
            }

            .owl-input-actions { display: flex; align-items: center; gap: 8px; margin-left: 8px; }
            .owl-send-btn { 
                background: #4f46e5; color: white; 
                width: 32px; height: 32px; 
                border-radius: 6px; border: none; 
                display: flex; align-items: center; justify-content: center;
                cursor: pointer; transition: background 0.2s;
            }
            .owl-send-btn:hover { background: #4338ca; }
            
            .owl-footer-hint {
                display: flex; justify-content: flex-end; gap: 15px;
                font-size: 11px; color: #94a3b8; margin-top: 8px;
            }

            /* Config Form */
            .owl-config-form {
                background: white;
                padding: 15px;
                border-radius: 8px;
                border: 1px solid #e2e8f0;
                margin-top: 10px;
                display: flex; flex-direction: column; gap: 10px;
            }
            .owl-config-form label { font-size: 12px; font-weight: 600; color: #64748b; margin-bottom: 4px; display: block; }
            .owl-config-form select, .owl-config-form input {
                width: 100%; padding: 8px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 13px;
                background: var(--control-bg, #fff); color: var(--text-color);
            }
            .owl-config-save {
                background: #0f172a; color: white; border: none; padding: 8px; border-radius: 6px;
                cursor: pointer; font-size: 13px; font-weight: 500; margin-top: 5px;
            }
            .owl-config-save:hover { background: #1e293b; }

            /* Preview */
            .owl-preview-area { display: flex; gap: 8px; margin-bottom: 8px; padding-bottom: 4px; overflow-x: auto; }
            .owl-preview-img { height: 60px; border-radius: 6px; border: 1px solid #ddd; object-fit: cover; }
            
            /* List Results */
            .owl-list-results { display: flex; flex-direction: column; gap: 8px; margin-top: 8px; }
            .owl-list-item { 
                background: white; border: 1px solid #e2e8f0; padding: 10px; border-radius: 8px; 
                cursor: pointer; transition: all 0.2s;
            }
            .owl-list-item:hover { border-color: #6366f1; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
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
        this.$modal.find('#owl-input').on('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.send_message();
            }
        });

        // New Chat
        this.$modal.find('.owl-new-chat').on('click', () => this.start_new_conversation());
        // History
        this.$modal.find('.owl-history').on('click', () => this.show_conversation_history());
        
        // Voice
        this.setup_voice();
        // Paste
        this.$modal.find('#owl-input').on('paste', (e) => this.handle_paste(e));
    }

    toggle() {
        this.is_open = !this.is_open;
        if (this.is_open) {
            this.$modal.removeClass('hidden');
            setTimeout(() => this.$modal.find('#owl-input').focus(), 50);
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
        frappe.call({
            method: 'tb_owlai_core.api.router.get_conversations',
            args: { limit: 10 },
            callback: (r) => {
                if (r.message && r.message.length > 0) {
                    this.render_conversation_list(r.message);
                } else {
                    frappe.msgprint("No history found.");
                }
            }
        });
    }

    render_conversation_list(conversations) {
        let html = '<div class="list-group">';
        conversations.forEach(conv => {
            const date = frappe.datetime.prettyDate(conv.modified);
            html += `
                <a class="list-group-item conv-item" data-id="${conv.name}" style="cursor: pointer;">
                    <div class="d-flex justify-content-between">
                        <h6 class="mb-1">${conv.title || 'Conversation ' + conv.name.slice(-4)}</h6>
                        <small>${date}</small>
                    </div>
                </a>`;
        });
        html += '</div>';
        
        const dialog = new frappe.ui.Dialog({
            title: 'Conversation History',
            fields: [{ fieldtype: 'HTML', fieldname: 'list', options: html }]
        });
        
        dialog.show();
        dialog.$wrapper.find('.conv-item').on('click', (e) => {
            const id = $(e.currentTarget).data('id');
            this.save_conversation_id(id);
            this.$modal.find('#owl-messages').empty();
            this.add_message("Switched conversation.", 'system');
            dialog.hide();
        });
    }

    // === Messaging ===
    
    add_message(html, role) {
        const $msgs = this.$modal.find('#owl-messages');
        $(`<div class="message ${role}">${html}</div>`).appendTo($msgs);
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
        
        const formData = new FormData();
        if(text) formData.append('text', text);
        if(imageFile) formData.append('image', imageFile);
        if(audioBlob) formData.append('audio', audioBlob, 'voice.wav');
        formData.append('route', frappe.get_route_str());
        if(this.conversation_id) formData.append('conversation_id', this.conversation_id);

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

        if (data.conversation_id) this.save_conversation_id(data.conversation_id);

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
            frappe.set_route(data.view || 'List', data.doctype);
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
