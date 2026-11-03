(() => {
    const form = document.querySelector('.wishlist-search');
    const results = document.querySelector('#wishlist-results');
    if (!form || !results) return;
    const input = form.querySelector('input[name="q"]');
    const submit = form.querySelector('button[type="submit"]');
    const status = document.querySelector('#wishlist-search-status');
    const clear = form.querySelector('a') || document.createElement('a');
    clear.textContent = 'Clear';
    clear.href = form.action;
    form.querySelector('div').append(clear);
    submit.hidden = true;
    clear.hidden = !input.value;
    let timer, controller, revision = 0, composing = false;

    function schedule(delay = 180) {
        clearTimeout(timer);
        controller?.abort();
        const current = ++revision;
        clear.hidden = !input.value;
        results.setAttribute('aria-busy', 'true');
        timer = setTimeout(() => update(current), delay);
    }

    async function update(current) {
        const url = new URL(form.action, window.location.href);
        // Preserve the library journey while resetting pagination for a new query.
        const origin = form.querySelector('input[name="from"]');
        if (origin) url.searchParams.set('from', origin.value);
        url.searchParams.delete('page');
        const query = input.value.trim();
        if (query) url.searchParams.set('q', query);
        else url.searchParams.delete('q');
        controller = new AbortController();
        try {
            const response = await fetch(url, {signal: controller.signal});
            if (!response.ok || response.redirected) throw new Error('Wishlist unavailable');
            const page = new DOMParser().parseFromString(await response.text(), 'text/html');
            const next = page.querySelector('#wishlist-results');
            if (!next) throw new Error('Missing wishlist results');
            if (current !== revision) return;
            results.replaceChildren(...next.childNodes);
            results.dataset.count = next.dataset.count;
            window.history.replaceState(null, '', url);
            document.dispatchEvent(new CustomEvent('collection:updated'));
            status.textContent = `${next.dataset.count} ${next.dataset.count === '1' ? 'game' : 'games'} found.`;
            submit.hidden = true;
            if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
                results.animate([{opacity: .4}, {opacity: 1}], {duration: 180, easing: 'ease-out'});
            }
        } catch (error) {
            if (current !== revision || error.name === 'AbortError') return;
            status.textContent = 'Could not update your wishlist. Try Search again.';
            submit.hidden = false;
        } finally {
            if (current === revision) results.setAttribute('aria-busy', 'false');
        }
    }
    input.addEventListener('input', () => { if (!composing) schedule(); });
    input.addEventListener('compositionstart', () => {
        composing = true;
        clearTimeout(timer);
        controller?.abort();
        revision++;
        results.setAttribute('aria-busy', 'false');
    });
    input.addEventListener('compositionend', () => { composing = false; schedule(); });
    form.addEventListener('submit', event => { event.preventDefault(); schedule(0); });
    clear.addEventListener('click', event => {
        event.preventDefault();
        input.value = '';
        input.focus();
        schedule(0);
    });
})();
