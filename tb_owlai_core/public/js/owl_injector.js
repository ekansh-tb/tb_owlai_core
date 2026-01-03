// 🦉 OwlAI Injector


$(document).ready(function() {
    if (typeof frappe === 'undefined') return;

    // Initialize Chat
    window.owl_chat = new OwlChat();
    console.log("🦉 OwlAI Chat Loaded");

    // 1. GLOBAL PASTE LISTENER (Images)
    document.addEventListener('paste', (event) => {
        // Don't trigger if user is typing in a text box (unless it's our own input, which is handled inside OwlChat)
        if (event.target.tagName === 'INPUT' || event.target.tagName === 'TEXTAREA') return;

        const items = (event.clipboardData || event.originalEvent.clipboardData).items;
        for (let index in items) {
            const item = items[index];
            if (item.kind === 'file' && item.type.includes('image')) {
                frappe.confirm('🦉 OwlAI: Analyze this image in Chat?', () => {
                    window.owl_chat.toggle(); // Open chat
                    window.owl_chat.add_attachment(item.getAsFile()); // Add file
                });
            }
        }
    });

    // 2. GLOBAL SHORTCUT (Command+Shift+L / Ctrl+Shift+L)
    frappe.ui.keys.add_shortcut({
        shortcut: 'shift+ctrl+l',
        action: () => {
            window.owl_chat.toggle();
        },
        description: 'Open OwlAI Assistant'
    });
});
