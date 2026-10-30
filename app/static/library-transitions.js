"use strict";
// Native document navigation preserves forms, focus, history and normal links.
(() => {
    const root = document.documentElement;
    const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
    function prepare(event) {
        const transition = event.viewTransition;
        if (!transition) return;
        if (motion.matches) {
            transition.skipTransition();
            return;
        }
        root.dataset.libraryNavigation = 'true';
        transition.finished.catch(() => {}).finally(() => {
            delete root.dataset.libraryNavigation;
        });
    }
    window.addEventListener('pageswap', prepare);
    window.addEventListener('pagereveal', prepare);
})();
