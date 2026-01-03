// 🦉 OwlAI Injector
$(document).ready(function() {
    if (typeof frappe === 'undefined') return;

    console.log("🦉 OwlAI Loaded");

    // 1. GLOBAL PASTE LISTENER (Images)
    document.addEventListener('paste', (event) => {
        // Don't trigger if user is typing in a text box
        if (event.target.tagName === 'INPUT' || event.target.tagName === 'TEXTAREA') return;

        const items = (event.clipboardData || event.originalEvent.clipboardData).items;
        for (let index in items) {
            const item = items[index];
            if (item.kind === 'file' && item.type.includes('image')) {
                frappe.confirm('🦉 OwlAI: Analyze this image?', () => {
                    upload_and_process(item.getAsFile());
                });
            }
        }
    });

    // 2. GLOBAL SHORTCUT (Command+Shift+L / Ctrl+Shift+L)
    frappe.ui.keys.add_shortcut({
        shortcut: 'shift+ctrl+l',
        action: () => {
            frappe.prompt([{'label': 'What do you want to do?', 'fieldname': 'value', 'fieldtype': 'Data'}], (values) => {
                call_router(null, values.value);
            }, '🦉 OwlAI Assistant', 'Go');
        },
        description: 'OwlAI Assistant'
    });

    function upload_and_process(file) {
        let formData = new FormData();
        formData.append('file', file, 'pasted_image.png');
        
        // Standard Frappe Upload
        fetch('/api/method/upload_file', {
            method: 'POST',
            headers: {
                'X-Frappe-CSRF-Token': frappe.csrf_token
            },
            body: formData
        })
        .then(r => r.json())
        .then(res => {
            if (res.message && res.message.file_url) {
                call_router(res.message.file_url, null);
            }
        });
    }

    function call_router(file_url, text) {
        frappe.msgprint("🦉 Thinking...");
        frappe.call({
            method: 'tb_owlai_core.api.router.handle_input',
            args: {
                file_url: file_url,
                text_query: text,
                current_route: frappe.get_route_str()
            },
            callback: (r) => {
                const action = r.message;
                if (action.action === 'create_doc') {
                    frappe.model.with_doctype(action.doctype, () => {
                        let doc = frappe.model.get_new_doc(action.doctype);
                        Object.assign(doc, action.data);
                        frappe.set_route('Form', action.doctype, doc.name);
                        frappe.msgprint(`🦉 Drafted ${action.doctype} for you!`);
                    });
                }
            }
        });
    }
});
