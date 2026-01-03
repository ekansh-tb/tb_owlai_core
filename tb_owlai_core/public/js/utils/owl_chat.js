window.OwlChat = class OwlChat {
    constructor() {
        this.socket = null;
        this.setup_ui();
        this.bind_events();
    }

    setup_ui() {
        // 1. Floating Action Button (FAB)
        this.$fab = $(`
            <div id="owl-fab" class="owl-fab">
                <span style="font-size: 24px;">🦉</span>
            </div>
        `).appendTo('body');

        // 2. Chat Window
        this.$window = $(`
            <div id="owl-chat-window" class="owl-chat-window hidden">
                <div class="owl-header">
                    <span>OwlAI Assistant</span>
                    <span class="owl-close">&times;</span>
                </div>
                <div class="owl-messages" id="owl-messages">
                    <div class="message system">
                        Hello! I'm your AI Workspace Assistant. I can see what you see.
                        <br>Try: <i>"Create a Task for reviewing this document"</i>
                    </div>
                </div>
                <div class="owl-input-area">
                    <div class="owl-preview-area hidden" id="owl-preview">
                        <!-- Image Preview -->
                    </div>
                    <div class="owl-input-wrapper">
                        <textarea id="owl-input" placeholder="Ask me anything... (or paste image)"></textarea>
                        <button id="owl-mic-btn" class="owl-btn-icon">🎤</button>
                        <button id="owl-send-btn" class="owl-send-btn">➤</button>
                    </div>
                </div>
            </div>
        `).appendTo('body');

        // Add Styles
        this.add_styles();
    }

    add_styles() {
        const css = `
            .owl-fab {
                position: fixed;
                bottom: 30px;
                right: 30px;
                width: 60px;
                height: 60px;
                background: linear-gradient(135deg, #6366f1, #8b5cf6);
                border-radius: 50%;
                box-shadow: 0 4px 15px rgba(0,0,0,0.2);
                display: flex;
                align-items: center;
                justify-content: center;
                cursor: pointer;
                z-index: 10000;
                transition: transform 0.2s;
            }
            .owl-fab:hover { transform: scale(1.1); }
            
            .owl-chat-window {
                position: fixed;
                bottom: 100px;
                right: 30px;
                width: 380px;
                height: 500px;
                background: var(--card-bg, #fff);
                border-radius: 16px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.15);
                display: flex;
                flex-direction: column;
                z-index: 10000;
                overflow: hidden;
                border: 1px solid var(--border-color, #eee);
            }
            .owl-chat-window.hidden { display: none; }
            
            .owl-header {
                padding: 15px;
                background: var(--bg-light-gray, #f8f8f8);
                border-bottom: 1px solid var(--border-color, #eee);
                font-weight: bold;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            .owl-close { cursor: pointer; font-size: 20px; }
            
            .owl-messages {
                flex: 1;
                padding: 15px;
                overflow-y: auto;
                display: flex;
                flex-direction: column;
                gap: 10px;
            }
            
            .message {
                max-width: 80%;
                padding: 10px 14px;
                border-radius: 12px;
                font-size: 14px;
                line-height: 1.4;
            }
            .message.system { align-self: center; background: #e0e7ff; color: #3730a3; text-align: center; width: 90%; }
            .message.user { align-self: flex-end; background: #6366f1; color: white; border-bottom-right-radius: 2px; }
            .message.assistant { align-self: flex-start; background: var(--bg-light-gray, #f3f4f6); color: var(--text-color, #1f2937); border-bottom-left-radius: 2px; }
            .message img { max-width: 100%; border-radius: 8px; margin-top: 5px; }
            
            .owl-input-area {
                padding: 10px;
                border-top: 1px solid var(--border-color, #eee);
                background: var(--card-bg, #fff);
            }
            
            .owl-preview-area {
                padding: 5px;
                margin-bottom: 5px;
                display: flex;
                gap: 5px;
                overflow-x: auto;
            }
            .owl-preview-img { height: 50px; border-radius: 4px; border: 1px solid #ddd; }
            
            .owl-input-wrapper { display: flex; gap: 8px; align-items: flex-end; }
            
            #owl-input {
                flex: 1;
                border: 1px solid var(--border-color, #ddd);
                border-radius: 8px;
                padding: 8px;
                resize: none;
                height: 40px;
                max-height: 100px;
                font-family: inherit;
                background: var(--input-bg, #fff);
                color: var(--text-color, #000);
            }
            
            .owl-btn-icon {
                background: none;
                border: none;
                font-size: 20px;
                cursor: pointer;
                padding: 8px;
                border-radius: 50%;
            }
            .owl-btn-icon:hover { background: var(--bg-light-gray, #f3f4f6); }
            .owl-btn-icon.recording { color: red; animation: pulse 1s infinite; }
            
            .owl-send-btn {
                background: #6366f1;
                color: white;
                border: none;
                border-radius: 8px;
                width: 40px;
                height: 40px;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            
            @keyframes pulse { 0% { transform: scale(1); } 50% { transform: scale(1.1); } 100% { transform: scale(1); } }
        `;
        $('<style>').text(css).appendTo('head');
    }

    bind_events() {
        // Toggle
        this.$fab.on('click', () => this.toggle());
        this.$window.find('.owl-close').on('click', () => this.toggle());

        // Send Text
        this.$window.find('#owl-send-btn').on('click', () => this.send_message());
        this.$window.find('#owl-input').on('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.send_message();
            }
        });

        // Voice
        this.setup_voice();

        // Paste (Image)
        // Global Paste Listener is handled by injector, but we can also listen locally on the input
        this.$window.find('#owl-input').on('paste', (e) => this.handle_paste(e));
    }

    toggle() {
        this.$window.toggleClass('hidden');
        if (!this.$window.hasClass('hidden')) {
            setTimeout(() => this.$window.find('#owl-input').focus(), 100);
        }
    }

    setup_voice() {
        if (!this.$window.find('#owl-mic-btn').length) return;

        const $mic = this.$window.find('#owl-mic-btn');
        let mediaRecorder;
        let audioChunks = [];

        $mic.on('click', async () => {
            if ($mic.hasClass('recording')) {
                // Stop Recording
                if (mediaRecorder && mediaRecorder.state !== 'inactive') {
                    mediaRecorder.stop();
                }
                $mic.removeClass('recording');
            } else {
                // Security Check (Allow localhost)
                const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
                if (!window.isSecureContext && !isLocal) {
                    frappe.msgprint("🎤 Microphone requires HTTPS or localhost. Please check your browser settings or use a secure connection.");
                    return;
                }

                // Start Recording
                try {
                    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                    mediaRecorder = new MediaRecorder(stream);
                    audioChunks = [];

                    mediaRecorder.ondataavailable = event => {
                        audioChunks.push(event.data);
                    };

                    mediaRecorder.onstop = () => {
                        const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                        console.log("OwlAI: Voice Captured", audioBlob.size, "bytes");
                        this.handle_voice_input(audioBlob);
                        stream.getTracks().forEach(track => track.stop());
                    };

                    mediaRecorder.start();
                    $mic.addClass('recording');
                } catch (err) {
                    console.error("OwlAI Mic Error:", err);
                    if (err.name === 'NotAllowedError') {
                         frappe.msgprint("🎤 Access blocked. Please allow microphone access in your browser.");
                    } else {
                         frappe.msgprint("Could not access microphone: " + err.message);
                    }
                }
            }
        });
    }

    handle_paste(event) {
        const items = (event.originalEvent || event).clipboardData.items;
        for (let index in items) {
            const item = items[index];
            if (item.kind === 'file' && item.type.includes('image')) {
                const blob = item.getAsFile();
                this.add_attachment(blob);
            }
        }
    }

    add_attachment(file) {
        this.current_attachment = file;
        const url = URL.createObjectURL(file);
        const $preview = this.$window.find('#owl-preview').removeClass('hidden');
        $preview.empty().append(`<img src="${url}" class="owl-preview-img">`);
    }

    handle_voice_input(audioBlob) {
        // Send audio blob to backend
        this.add_message("🎤 Audio sent...", 'user');
        this.process_request(null, null, audioBlob);
    }

    send_message() {
        const $input = this.$window.find('#owl-input');
        const text = $input.val().trim();
        
        if (!text && !this.current_attachment) return;

        // UI Update
        if (text) this.add_message(text, 'user');
        if (this.current_attachment) {
            const url = URL.createObjectURL(this.current_attachment);
            this.add_message(`<img src="${url}">`, 'user');
        }

        this.process_request(text, this.current_attachment);

        // Reset
        $input.val('');
        this.current_attachment = null;
        this.$window.find('#owl-preview').addClass('hidden').empty();
    }

    add_message(html, role) {
        const $msgs = this.$window.find('#owl-messages');
        $(`<div class="message ${role}">${html}</div>`).appendTo($msgs);
        $msgs.scrollTop($msgs[0].scrollHeight);
    }

    process_request(text, imageFile, audioBlob) {
        this.add_message('Thinking...', 'assistant loading');
        console.log("OwlAI: Sending Request...", { text, hasImage: !!imageFile, hasAudio: !!audioBlob });
        
        const formData = new FormData();
        if (text) formData.append('text', text);
        if (imageFile) formData.append('image', imageFile);
        if (audioBlob) formData.append('audio', audioBlob, 'voice_command.wav');
        
        formData.append('route', frappe.get_route_str());

        // We need a custom upload endpoint that can handle this mixed content
        // Or we use frappe.call for text, and upload_file for files.
        // Better: Use a single unified custom API endpoint.
        
        fetch('/api/method/tb_owlai_core.api.router.handle_input_v2', {
            method: 'POST',
            headers: { 'X-Frappe-CSRF-Token': frappe.csrf_token },
            body: formData
        })
        .then(r => r.json())
        .then(res => this.handle_response(res))
        .catch(err => {
            this.remove_loading();
            this.add_message("Error: " + err.message, 'assistant');
        });
    }

    handle_response(res) {
        this.remove_loading();
        
        // Handle Error
        if (res.exc) {
            console.error(res.exc);
            // Try to extract a friendly message if possible, otherwise generic
            this.add_message("⚠️ An backend error occurred. Check browser console.", 'assistant');
            return;
        }

        const data = res.message;
        
        if (!data) {
             this.add_message("⚠️ Received empty response.", 'assistant');
             return;
        }

        // 1. Text Response
        if (data.reply) {
            this.add_message(frappe.markdown(data.reply), 'assistant');
        }

        // 2. Action Execution
        if (data.action === 'create_doc') {
             frappe.model.with_doctype(data.doctype, () => {
                let doc = frappe.model.get_new_doc(data.doctype);
                Object.assign(doc, data.data);
                frappe.set_route('Form', data.doctype, doc.name);
                this.add_message(`Drafted ${data.doctype} for you!`, 'assistant');
            });
        } else if (data.action === 'navigate') {
            frappe.set_route(data.view || 'List', data.doctype);
            this.add_message(`Navigating to ${data.doctype}...`, 'assistant');
        }
    }

    remove_loading() {
        this.$window.find('.message.loading').remove();
    }
}
