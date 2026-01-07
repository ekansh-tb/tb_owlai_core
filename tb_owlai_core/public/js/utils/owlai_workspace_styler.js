frappe.router.on('change', () => {
    const route = frappe.get_route();
    if (route[0] === 'workspaces' && route[1] && route[1].toLowerCase() === 'owlai') {
        $('body').addClass('owlai-workspace');
    } else {
        $('body').removeClass('owlai-workspace');
    }
});

// Initial check
$(document).ready(() => {
    const route = frappe.get_route();
    if (route[0] === 'workspaces' && route[1] && route[1].toLowerCase() === 'owlai') {
        $('body').addClass('owlai-workspace');
    }
});
