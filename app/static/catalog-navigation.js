"use strict";
(() => {
    let pending = null;
    function go(destination) {
        const url = new URL(destination, window.location.origin);
        if (url.origin !== window.location.origin || !/^\/(?:explore\/games\/[1-9]\d*|games\/[1-9]\d*\/[a-z0-9-]+)$/.test(url.pathname)) return false;
        if (pending !== null) return true;
        if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
            window.location.assign(url.href);
            return true;
        }
        document.body.classList.add("is-opening-game");
        pending = window.setTimeout(() => window.location.assign(url.href), 180);
        return true;
    }
    window.VestigiumCatalogNavigation = { go };
    document.addEventListener("click", (event) => {
        if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
        const link = event.target.closest("a[href]");
        if (!link || link.hasAttribute("download") || (link.target && link.target !== "_self")) return;
        if (go(link.href)) event.preventDefault();
    });
    window.addEventListener("pageshow", () => {
        window.clearTimeout(pending);
        pending = null;
        document.body.classList.remove("is-opening-game");
    });
})();
