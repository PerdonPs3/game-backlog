(() => {
    'use strict';
    let pending;
    let generation = 0;
    async function update(url, direction, push = true) {
        const current = document.querySelector('[data-catalog-pages]');
        if (!current) return;
        pending?.abort();
        const controller = new AbortController();
        pending = controller;
        const version = ++generation;
        const status = current.querySelector('[data-catalog-page-status]');
        current.setAttribute('aria-busy', 'true');
        status.className = 'visually-hidden';
        status.textContent = 'Loading games…';
        try {
            const response = await fetch(url, {signal: controller.signal, credentials: 'same-origin', headers: {Accept: 'text/html'}});
            if (response.redirected) { window.location.assign(response.url); return; }
            const html = await response.text();
            if (version !== generation) return;
            if (!response.ok) throw new Error('unavailable');
            const replacement = new DOMParser().parseFromString(html, 'text/html').querySelector('[data-catalog-pages]');
            if (!replacement) throw new Error('invalid');
            const previousScroll = window.scrollY;
            current.replaceWith(replacement);
            document.dispatchEvent(new Event('collection:updated'));
            if (push) history.pushState({}, '', url);
            const picker = document.querySelector('[data-catalog-url]');
            if (picker?.dataset) picker.dataset.origin = window.location.pathname + window.location.search;
            replacement.querySelector('[data-catalog-page-status]').textContent = 'Games updated.';
            if (direction === 'next') {
                const results = replacement.querySelector('.catalog-results-heading');
                if (results) {
                    const header = document.querySelector('.workspace-site-header');
                    const offset = Math.max(0, header?.getBoundingClientRect().bottom || 0) + 8;
                    replacement.querySelector('.catalog-grid a')?.focus({preventScroll: true});
                    window.scrollTo({top: Math.max(0, window.scrollY + results.getBoundingClientRect().top - offset),
                        behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'});
                }
            } else {
                window.scrollTo({top: previousScroll, behavior: 'instant'});
            }
        } catch (error) {
            if (error.name !== 'AbortError' && version === generation) {
                status.className = 'catalog-message';
                status.textContent = 'Could not load this page. Your previous games are still here. Please try again.';
            }
        } finally {
            if (version === generation) document.querySelector('[data-catalog-pages]')?.removeAttribute('aria-busy');
        }
    }
    document.addEventListener('click', event => {
        const link = event.target.closest('a[data-catalog-page]');
        if (!link || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        update(link.href, link.dataset.catalogPage);
    });
    window.addEventListener('popstate', () => update(window.location.href, null, false));
})();
