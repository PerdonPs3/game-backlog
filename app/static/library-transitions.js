"use strict";
// Native document navigation preserves forms, focus, history and normal links.
(() => {
    const root = document.documentElement;
    const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
    const rooms = ['/library', '/library/wishlist', '/library/lists', '/library/pick'];
    const artwork = ['library', 'wishlist-observatory', 'lists-study', 'games-salon'];
    const prepared = new Map();
    let active;
    let pending = 0;
    let departing = false;
    let queuedDestination = null;
    function warmRoom(index) {
        const theme = root.dataset.theme === 'light' ? 'day' : 'night';
        const url = new URL(`images/backgrounds/${artwork[index]}-${theme}.webp`, scriptRoot);
        if (!prepared.has(url.href)) {
            const image = new Image();
            image.src = url.href;
            const ready = image.decode().then(() => true, () => false);
            // Keep the decoded image alive for this document's navigation.
            prepared.set(url.href, { image, ready });
        }
        return prepared.get(url.href).ready;
    }
    const scriptRoot = new URL('.', document.currentScript.src);
    function tabLink(event) {
        const link = event.target.closest?.('.section-navigation a');
        if (!link || link.hasAttribute('download') || (link.target && link.target !== '_self')) return null;
        return roomIndex(link.href) >= 0 ? link : null;
    }
    document.addEventListener('pointerover', event => {
        const link = tabLink(event);
        if (link) warmRoom(roomIndex(link.href));
    });
    document.addEventListener('focusin', event => {
        const link = tabLink(event);
        if (link) warmRoom(roomIndex(link.href));
    });
    document.addEventListener('click', async event => {
        if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        if (active && event.target.closest?.('[data-theme-toggle]')) {
            event.preventDefault();
            event.stopImmediatePropagation();
            return;
        }
        const link = tabLink(event);
        if (!link) return;
        if (active) {
            event.preventDefault();
            event.stopImmediatePropagation();
            if (!departing) {
                queuedDestination = link.href;
                warmRoom(roomIndex(link.href));
            }
            return;
        }
        if (departing) {
            event.preventDefault();
            event.stopImmediatePropagation();
            await navigate(link.href);
            return;
        }
        if (roomIndex(link.href) === roomIndex(window.location.href) || motion.matches || !('onpageswap' in window)) return;
        event.preventDefault();
        await navigate(link.href);
    }, { capture: true });
    async function navigate(destination) {
        const ticket = ++pending;
        let timeout;
        await Promise.race([
            warmRoom(roomIndex(destination)),
            new Promise(resolve => timeout = setTimeout(resolve, 1200)),
        ]);
        clearTimeout(timeout);
        if (ticket !== pending) return;
        departing = true;
        window.location.assign(destination);
    }
    function roomIndex(url) {
        if (!url) return -1;
        const destination = new URL(url, window.location.href);
        return destination.origin === window.location.origin ? rooms.indexOf(destination.pathname) : -1;
    }
    function prepare(event) {
        if (event.type === 'pageswap') queuedDestination = null;
        const transition = event.viewTransition;
        if (!transition) return;
        transition.ready?.catch(() => {});
        const activation = event.type === 'pageswap' ? event.activation : window.navigation?.activation;
        const from = roomIndex(activation?.from?.url);
        const to = roomIndex(activation?.entry?.url);
        if (motion.matches || from < 0 || to < 0 || from === to) {
            transition.skipTransition();
            return;
        }
        active = transition;
        root.dataset.libraryNavigation = 'true';
        root.dataset.libraryDirection = to > from ? 'forward' : 'backward';
        transition.finished.catch(() => {}).finally(async () => {
            if (active !== transition) return;
            delete root.dataset.libraryNavigation;
            delete root.dataset.libraryDirection;
            if (event.type === 'pagereveal') {
                // Paint the real destination before another snapshot can start.
                await new Promise(resolve => window.requestAnimationFrame(() => window.requestAnimationFrame(resolve)));
            }
            if (active !== transition) return;
            active = null;
            const destination = queuedDestination;
            queuedDestination = null;
            if (destination && destination !== window.location.href && !departing) await navigate(destination);
        });
    }
    window.addEventListener('pageswap', prepare);
    window.addEventListener('pagereveal', prepare);
    window.addEventListener('pageshow', () => {
        departing = false;
        pending++;
    });
    // Warm only static artwork for the selected theme, never private HTML/data.
    document.addEventListener('DOMContentLoaded', () => {
        const warm = () => {
            if (window.navigator?.connection?.saveData) return;
            rooms.forEach((room, index) => warmRoom(index));
        };
        if (window.requestIdleCallback) window.requestIdleCallback(warm, { timeout: 1500 });
        else setTimeout(warm, 200);
    }, { once: true });
    motion.addEventListener?.('change', event => {
        if (event.matches) active?.skipTransition();
    });
})();
