"use strict";

(() => {
    const root = document.documentElement;
    const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    function prepare(event) {
        const transition = event.viewTransition;
        if (!transition) return;
        if (motion.matches) {
            transition.skipTransition();
            return;
        }
        root.dataset.roomNavigation = "true";
        const clear = () => { delete root.dataset.roomNavigation; };
        transition.finished.then(clear, clear);
    }
    window.addEventListener("pageswap", prepare);
    window.addEventListener("pagereveal", prepare);
})();
