// ASP-FEAT-ASP-04 v1.0 I-DOC-10 — dashboard doc review helpers.
// pdf.js rendering is done inline in _review_panel.html via an IIFE
// because the canvas element arrives via HTMX swap and the inline
// script runs after the swap completes. This file currently carries
// only the common upload-form hint-preview — pdf.js orchestration
// lives co-located with the canvas for init ordering guarantees.

(function initDashboardHelpers() {
    const form = document.getElementById('upload-form');
    if (!form) return;

    // Show a warning if the user has not set ASP_API_KEY in
    // localStorage. Dashboard auth uses the same header as the API.
    if (!window.localStorage.getItem('ASP_API_KEY')) {
        const hint = document.createElement('p');
        hint.className = 'subtle';
        hint.innerHTML =
            'Tip: set your API key via the browser console: '
            + '<code>localStorage.setItem("ASP_API_KEY", "asp_...")</code>';
        form.parentNode.insertBefore(hint, form);
    }
})();
