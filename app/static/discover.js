(() => {
    'use strict';
    let pending;
    let generation = 0;
    async function update(url, push = true) {
        const current = document.querySelector('[data-discover]');
        if (!current) return;
        pending?.abort();
        const controller = new AbortController();
        pending = controller;
        const version = ++generation;
        const status = current.querySelector('[data-discover-status]');
        current.querySelector('.discover-results').setAttribute('aria-busy', 'true');
        status.textContent = 'Finding your next adventure…';
        try {
            const response = await fetch(url, {signal: controller.signal, credentials: 'same-origin', headers: {Accept: 'text/html'}});
            if (response.redirected) { window.location.assign(response.url); return; }
            const html = await response.text();
            if (version !== generation) return;
            if (!response.ok) throw new Error('unavailable');
            const replacement = new DOMParser().parseFromString(html, 'text/html').querySelector('[data-discover]');
            if (!replacement) throw new Error('invalid');
            const activeName = document.activeElement?.name;
            const activeValue = document.activeElement?.type === 'radio' ? document.activeElement.value : null;
            current.replaceWith(replacement);
            document.dispatchEvent(new Event('collection:updated'));
            if (push) history.pushState({}, '', url);
            replacement.querySelector('[data-discover-status]').textContent = 'Recommendations updated.';
            if (activeName) {
                const selector = `[name="${activeName}"]${activeValue === null ? '' : `[value="${activeValue}"]`}`;
                replacement.querySelector(selector)?.focus({preventScroll: true});
            }
        } catch (error) {
            if (error.name !== 'AbortError' && version === generation) {
                status.textContent = 'Could not update recommendations. Your previous results are still here. Try again.';
            }
        } finally {
            if (version === generation) document.querySelector('.discover-results')?.removeAttribute('aria-busy');
        }
    }
    document.addEventListener('submit', event => {
        const form = event.target.closest('[data-discover-filters]');
        if (!form) return;
        event.preventDefault();
        const url = new URL(form.action);
        url.search = new URLSearchParams(new FormData(form)).toString();
        update(url.href);
    });
    document.addEventListener('change', event => {
        if (!event.target.closest('[data-discover-filters]')) return;
        pending?.abort();
        generation++;
        document.querySelector('.discover-results')?.removeAttribute('aria-busy');
        document.querySelector('[data-discover-status]').textContent = 'Apply your filters to update these results.';
        if (event.target.name === 'mode') event.target.closest('[data-discover-filters]').requestSubmit();
    });
    document.addEventListener('click', event => {
        const link = event.target.closest('a[data-discover-link]');
        if (!link || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        update(link.href);
    });
    window.addEventListener('popstate', () => update(window.location.href, false));
})();
