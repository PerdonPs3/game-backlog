(() => {
    'use strict';
    let pending;
    let generation = 0;
    const saving = new WeakSet();
    const saved = new Map();
    function showSaved(form, html) {
        const marker = new DOMParser().parseFromString(html, 'text/html').querySelector('.discover-saved');
        if (!marker) throw new Error('Invalid saved state.');
        const focused = form.contains(document.activeElement);
        form.replaceWith(marker);
        if (focused) marker.focus({preventScroll: true});
    }
    async function saveWish(form) {
        if (saving.has(form)) return;
        saving.add(form);
        const button = form.querySelector('button');
        const original = button.textContent;
        form.querySelector('[data-wish-error]')?.remove();
        button.disabled = true;
        button.textContent = 'Saving…';
        form.setAttribute('aria-busy', 'true');
        try {
            const response = await fetch(form.action, {method: 'POST', body: new FormData(form),
                credentials: 'same-origin', headers: {Accept: 'application/json'}});
            if (response.redirected) { window.location.assign(response.url); return; }
            const data = await response.json();
            if (!response.ok || !data.saved || !data.html) throw new Error(data.error || 'Could not save this game. Please try again.');
            saved.set(form.dataset.discoverWish, data.html);
            const visible = document.querySelector(`[data-discover-wish="${form.dataset.discoverWish}"]`);
            if (visible) showSaved(visible, data.html);
        } catch (error) {
            const message = document.createElement('p');
            message.dataset.wishError = '';
            message.className = 'discover-wish-error';
            message.setAttribute('role', 'alert');
            const detail = String(error.message || '');
            const expected = ['The catalog', 'Your wishlist', 'This game is already in your library.']
                .some(prefix => detail.startsWith(prefix));
            message.textContent = expected ? detail : 'Could not save this game. Please try again.';
            form.append(message);
        } finally {
            saving.delete(form);
            button.disabled = false;
            button.textContent = original;
            form.removeAttribute('aria-busy');
        }
    }
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
            for (const [id, html] of saved) {
                const form = replacement.querySelector(`[data-discover-wish="${id}"]`);
                if (form) showSaved(form, html);
            }
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
        const wish = event.target.closest('[data-discover-wish]');
        if (wish) { event.preventDefault(); saveWish(wish); return; }
        const form = event.target.closest('[data-discover-filters]');
        if (!form) return;
        event.preventDefault();
        const url = new URL(form.action);
        url.search = new URLSearchParams(new FormData(form)).toString();
        update(url.href);
    });
    document.addEventListener('change', event => {
        const form = event.target.closest('[data-discover-filters]');
        if (form) form.requestSubmit();
    });
    document.addEventListener('click', event => {
        const link = event.target.closest('a[data-discover-link]');
        if (!link || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        update(link.href);
    });
    window.addEventListener('popstate', () => update(window.location.href, false));
})();
