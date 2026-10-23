/* Refresh the browser-bound form token after long visits or account switches. */
(() => {
    document.querySelectorAll('[data-quick-add]').forEach(form => {
        if (!form.dataset.tokenUrl) return;
        const feedback = form.querySelector('[data-quick-feedback]');
        const token = form.querySelector('[name="csrf_token"]');
        let ready = false, pending = false;
        form.addEventListener('submit', async event => {
            if (ready) { ready = false; return; }
            event.preventDefault();
            if (pending) return;
            pending = true;
            form.setAttribute('aria-busy', 'true');
            feedback.hidden = false;
            feedback.textContent = 'Adding to your library…';
            try {
                const response = await fetch(form.dataset.tokenUrl, { credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' }, signal: AbortSignal.timeout(10000) });
                const result = await response.json();
                if (!response.ok || typeof result.csrf_token !== 'string' || !result.csrf_token) {
                    throw new Error(response.status === 401 ? 'Please sign in again using the link above, then retry.' : 'Your session could not be checked. Refresh the page and try again.');
                }
                token.value = result.csrf_token;
                ready = true;
                form.requestSubmit(event.submitter || undefined);
            } catch (error) {
                feedback.textContent = error.message.startsWith('Please sign in') || error.message.startsWith('Your session') ? error.message : 'Could not reach account services. Please try again.';
            } finally {
                pending = false;
                form.removeAttribute('aria-busy');
            }
        });
    });
})();
