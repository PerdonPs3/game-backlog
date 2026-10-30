"use strict";
// Native document navigation preserves forms, focus, history and normal links.
(() => {
    const root = document.documentElement;
    const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
    const rooms = ['/library', '/library/wishlist', '/library/lists', '/library/pick'];
    let active;
    function roomIndex(url) {
        if (!url) return -1;
        const destination = new URL(url, window.location.href);
        return destination.origin === window.location.origin ? rooms.indexOf(destination.pathname) : -1;
    }
    function prepare(event) {
        const transition = event.viewTransition;
        if (!transition) return;
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
        transition.finished.catch(() => {}).finally(() => {
            if (active !== transition) return;
            delete root.dataset.libraryNavigation;
            delete root.dataset.libraryDirection;
            active = null;
        });
    }
    window.addEventListener('pageswap', prepare);
    window.addEventListener('pagereveal', prepare);
    motion.addEventListener?.('change', event => {
        if (event.matches) active?.skipTransition();
    });
})();
