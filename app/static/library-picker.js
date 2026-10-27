"use strict";

(() => {
    const form = document.querySelector('.adventure-preferences');
    const genre = document.querySelector('#pick-genre');
    const outcome = document.querySelector('#pick-outcome');
    const feedback = document.querySelector('#pick-feedback');
    const submit = form?.querySelector('button[type=submit]');
    if (!form || !genre) return;
    form.addEventListener('change', (event) => {
        // The available genres are scoped to the selected states.
        if (event.target.name === 'status') genre.value = '';
    });
    if (!outcome || !feedback || !submit || typeof fetch !== 'function' || typeof FormData !== 'function') return;
    let pending = false;

    function revealResult() {
        outcome.style.minHeight = '';
        const result = document.querySelector('#adventure-result') || outcome;
        const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        result.scrollIntoView({ block: 'start', behavior: reduced ? 'auto' : 'smooth' });
        result.focus?.({ preventScroll: true });
    }

    async function pick() {
        if (pending || submit.disabled) return;
        pending = true;
        const query = new URLSearchParams(new FormData(form)).toString();
        const url = new URL(form.action, window.location.href);
        url.search = query;
        let spinning = false;
        submit.disabled = true;
        outcome.setAttribute('aria-busy', 'true');
        feedback.hidden = false;
        feedback.textContent = 'Finding your next game...';
        try {
            const response = await fetch(url, { headers: { Accept: 'application/json' } });
            if (!response.ok) throw new Error('Pick request failed.');
            const data = await response.json();
            if (typeof data.html !== 'string' || !Array.isArray(data.genres) || data.genres.some(value => typeof value !== 'string')) {
                throw new Error('Invalid pick response.');
            }
            if (new URLSearchParams(new FormData(form)).toString() !== query) {
                feedback.textContent = 'Preferences changed. Pick again to use them.';
                return;
            }
            const selectedGenre = genre.value;
            const options = [new Option('Any genre', '')];
            for (const value of data.genres) options.push(new Option(value, value));
            if (selectedGenre && !data.genres.includes(selectedGenre)) options.push(new Option(`${selectedGenre} (unavailable)`, selectedGenre));
            genre.replaceChildren(...options);
            genre.value = selectedGenre;
            // Only the same-origin, server-rendered, autoescaped result is inserted.
            outcome.style.minHeight = `${outcome.offsetHeight}px`;
            document.dispatchEvent(new Event('picker:replace'));
            outcome.innerHTML = data.html;
            try { window.history.replaceState(null, '', url); } catch { /* Picking still works without history access. */ }
            document.dispatchEvent(new Event('collection:updated'));
            submit.disabled = false;
            spinning = Boolean(window.startAdventureRoulette?.());
            feedback.hidden = true;
            if (!spinning) revealResult();
        } catch {
            feedback.textContent = 'Could not pick a game. Your previous result is still here. Please try again.';
        } finally {
            pending = false;
            outcome.setAttribute('aria-busy', 'false');
            if (!spinning) {
                submit.disabled = false;
                outcome.style.minHeight = '';
            }
        }
    }

    form.addEventListener('submit', (event) => {
        event.preventDefault();
        pick();
    });
    document.addEventListener('click', (event) => {
        if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
        const link = event.target.closest('[data-pick-again]');
        if (!link || link.hasAttribute('download') || (link.target && link.target !== '_self')) return;
        if (new URL(link.href, window.location.href).origin !== window.location.origin) return;
        event.preventDefault();
        pick();
    });
    document.addEventListener('picker:revealed', () => { outcome.style.minHeight = ''; });
})();
