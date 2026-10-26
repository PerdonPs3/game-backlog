"use strict";

(() => {
    const root = document.documentElement;
    const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    let currentTransition;
    function prepare(event, direction) {
        const transition = event.viewTransition;
        if (!transition) return;
        if (motion.matches) {
            transition.skipTransition();
            return;
        }
        currentTransition = transition;
        root.dataset.roomNavigation = direction;
        const clear = () => {
            if (currentTransition !== transition) return;
            delete root.dataset.roomNavigation;
            currentTransition = null;
        };
        transition.finished.then(clear, clear);
    }
    window.addEventListener("pageswap", (event) => prepare(event, "out"));
    window.addEventListener("pagereveal", (event) => prepare(event, "in"));
})();
