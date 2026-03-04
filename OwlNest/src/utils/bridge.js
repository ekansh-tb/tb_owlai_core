
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
        if (payload.action === 'navigate' || payload.name === 'navigate') {
            const baseUrl = window.location.origin;
            const doctype = payload.doctype;
            if (!doctype) return;

            // Frappe route for doctype list is /app/doctype (kebab-case)
            let slug = doctype.toLowerCase().replace(/ /g, '-');
            let targetUrl = `${baseUrl}/app/${slug}`;

            // Check if it's a specific document (Form view)
            const docname = payload.docname || (payload.filters && (payload.filters.name || payload.filters.id));

            if (docname) {
                targetUrl += `/${docname}`;
            }

            window.location.href = targetUrl;
        }
    }
}

export const bridge = new Bridge();
