
export class Bridge {
    constructor() {
        this.listeners = {};
        this.isEmbedded = new URLSearchParams(window.location.search).get('mode') === 'embedded';

        if (this.isEmbedded) {
            window.addEventListener('message', (event) => this.handleMessage(event));
        }
    }

    on(action, callback) {
        if (!this.listeners[action]) {
            this.listeners[action] = [];
        }
        this.listeners[action].push(callback);
    }

    handleMessage(event) {
        const { action, payload } = event.data;
        if (this.listeners[action]) {
            this.listeners[action].forEach(cb => cb(payload));
        }
    }

    send(action, payload) {
        if (this.isEmbedded) {
            window.parent.postMessage({ action, payload }, '*');
        } else {
            console.warn('Bridge.send ignored (not embedded):', action, payload);
            // Fallback for standalone mode if applicable (e.g., standard navigation)
            if (action === 'EXECUTE_ACTION' && payload.action === 'navigate') {
                this.handleStandaloneNavigation(payload);
            }
        }
    }

    handleStandaloneNavigation(payload) {
         // Standalone navigation fallback
         // Note: Frappe Router might need to be available or we open new tabs
         if (payload.action === 'navigate') {
             // If we are in standalone OwlNest, we might not have full Desk context.
             // Best effort: Open in new tab or use window.location if it's a known public route.
             const baseUrl = window.location.origin;
             let targetUrl = `${baseUrl}/app/${payload.doctype.toLowerCase().replace(/ /g, '-')}`;
             if (payload.name) {
                 targetUrl += `/${payload.name}`;
             }
             window.open(targetUrl, '_blank');
         }
    }
}

export const bridge = new Bridge();
