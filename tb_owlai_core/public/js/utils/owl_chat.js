/**
 * OwlAI Chat - Unified Bridge Client
 * Loads OwlNest (Vue App) in an Iframe and handles Desk-side Actions.
 */
window.OwlChat = class OwlChat {
    constructor() {
        this.is_open = false;
        this.iframe_loaded = false;

        // Wait for Frappe UI
        if (frappe.ui.toolbar) {
            this.setup();
        } else {
            $(document).on('toolbar_setup', () => this.setup());
        }
    }

    setup() {
        this.mount_navbar_icon();
        this.bind_global_shortcuts();
        window.addEventListener('message', (e) => this.handle_message(e));
    }

    toggle() {
        if (!this.iframe_loaded) {
            this.mount_iframe();
        }

        const $container = $('#owl-iframe-container');
        this.is_open = !this.is_open;

        if (this.is_open) {
            $container.removeClass('hidden');
            // Send updated context whenever opened
            this.send_context();
            // Focus iframe logic? (Hard to focus inside iframe from here without postMessage focus request)
        } else {
            $container.addClass('hidden');
        }
    }

    mount_iframe() {
        if ($('#owl-iframe-container').length) return;

        // Create Container & Iframe
        const $container = $(`
            <div id="owl-iframe-container" class="hidden" style="
                position: fixed; 
                top: 0; 
                left: 0; 
                width: 100vw; 
                height: 100vh; 
                z-index: 10001; 
                background: rgba(0,0,0,0.5); /* Slight dim for focus */
                backdrop-filter: blur(2px);
                display: flex;
                align-items: center;
                justify-content: center;
            ">
                <iframe id="owl-iframe" src="/owlnest?mode=embedded" style="
                    width: 100%; 
                    height: 100%; 
                    border: none; 
                    background: transparent;
                " allow="microphone; clipboard-read; clipboard-write"></iframe>
                
                <!-- Close Button (Outside Iframe) -->
                <button id="owl-close-overlay" style="
                    position: absolute;
                    top: 20px;
                    right: 20px;
                    background: rgba(0,0,0,0.5);
                    color: white;
                    border: 1px solid rgba(255,255,255,0.2);
                    border-radius: 50%;
                    width: 40px;
                    height: 40px;
                    cursor: pointer;
                    z-index: 10002;
                    display: flex; 
                    align-items: center; 
                    justify-content: center;
                ">✕</button>
            </div>
        `).appendTo('body');

        // Close on clicking outside (if we create a smaller modal, but here we fill screen)
        // or clicking close button
        $container.find('#owl-close-overlay').on('click', () => this.toggle());

        this.iframe_loaded = true;
    }

    mount_navbar_icon() {
        if ($('.owl-navbar-icon-li').length) return;
        const $navbar_right = $('.navbar .navbar-right .nav.navbar-nav');
        if (!$navbar_right.length) {
            setTimeout(() => this.mount_navbar_icon(), 1000);
            return;
        }

        const $li = $(`
            <li class="nav-item owl-navbar-icon-li" title="Ask OwlAI (Ctrl+K)">
                <a class="nav-link" href="#" onclick="return false;" style="display: flex; align-items: center; padding: 12px 10px;">
                    <span style="font-size: 18px; line-height: 1;">🦉</span>
                </a>
            </li>
        `);
        $navbar_right.prepend($li);
        $li.on('click', (e) => { e.preventDefault(); this.toggle(); });
    }

    bind_global_shortcuts() {
        // Ctrl+K / Cmd+K
        frappe.ui.keys.add_shortcut({
            shortcut: 'ctrl+k',
            action: () => this.toggle(),
            description: 'Open OwlAI'
        });
        frappe.ui.keys.add_shortcut({
            shortcut: 'ctrl+space',
            action: () => this.toggle(),
            description: 'Open OwlAI'
        });
    }

    // === Bridge Communication ===

    send_context() {
        if (!this.iframe_loaded) return;

        const iframe = document.getElementById('owl-iframe');
        if (!iframe) return;

        // Gather Context
        const context = {
            route: frappe.get_route_str(),
            // Safe doc extraction
            form_data: (window.cur_frm && window.cur_frm.doc) ? window.cur_frm.doc : null,
            // Selected list items
            selected_items: (window.cur_list && window.cur_list.get_checked_items) ? window.cur_list.get_checked_items(true) : []
        };

        iframe.contentWindow.postMessage({
            action: 'UPDATE_CONTEXT',
            payload: context
        }, '*');
    }

    handle_message(event) {
        // Security check: ensure origin matches if possible, but same-origin is implied mostly
        const { action, payload } = event.data;

        if (action === 'EXECUTE_ACTION') {
            this.handle_action(payload);
        } else if (action === 'CLOSE_CHAT') {
            this.toggle();
        }
    }

    handle_action(data) {
        console.log("OwlAI Bridge Action:", data);

        if (data.action === 'navigate') {
            if (data.route_options) frappe.route_options = data.route_options;

            if (data.name) {
                frappe.set_route(data.view || 'Form', data.doctype, data.name);
            } else {
                frappe.set_route(data.view || 'List', data.doctype);
            }

            // Optionally close chat?
            // this.toggle(); 
        }
        else if (data.action === 'create_doc') {
            frappe.model.with_doctype(data.doctype, () => {
                let doc = frappe.model.get_new_doc(data.doctype);
                Object.assign(doc, data.data || {});
                frappe.set_route('Form', data.doctype, doc.name);
                this.toggle();
            });
        }
        else if (data.action === 'reload') {
            frappe.ui.toolbar.clear_cache();
            frappe.router.reload();
        }
    }

    // Legacy support for older calls?
    add_attachment(file) {
        // TODO: Pass to iframe via PROMPT_WITH_ATTACHMENT action
        this.toggle();
        console.warn("Attachment passing to iframe not yet implemented.");
    }
}
