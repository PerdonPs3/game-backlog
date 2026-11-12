"use strict";

// Runs in <head>, before styles render, to avoid flashing the wrong theme.
(() => {
    const root = document.documentElement;
    const key = "game-backlog.theme";
    const system = window.matchMedia?.("(prefers-color-scheme: light)");
    const motion = window.matchMedia?.("(prefers-reduced-motion: reduce)");
    let transition;
    let preference = null;
    try {
        const saved = window.localStorage.getItem(key);
        if (saved === "light" || saved === "dark") preference = saved;
    } catch { /* The switch still works when storage is unavailable. */ }

    function render(theme) {
        root.dataset.theme = theme;
        for (const button of document.querySelectorAll("[data-theme-toggle]")) {
            const label = theme === "light" ? "Switch to dark mode" : "Switch to light mode";
            button.setAttribute("aria-label", label);
            button.setAttribute("title", label);
            button.hidden = false;
        }
    }
    function apply(animate = false) {
        const theme = preference || (system?.matches ? "light" : "dark");
        transition?.skipTransition();
        if (animate && theme !== root.dataset.theme && !motion?.matches && typeof document.startViewTransition === "function") {
            try {
                transition = document.startViewTransition(() => render(theme));
                transition.finished.catch(() => {});
                return;
            } catch { /* Regular CSS transitions remain the fallback. */ }
        }
        render(theme);
    }
    apply();
    // Reveal the header toggle before a cross-document transition captures it.
    window.addEventListener("pagereveal", () => render(root.dataset.theme));
    document.addEventListener("DOMContentLoaded", () => {
        apply();
        root.dataset.themeReady = "true";
        for (const button of document.querySelectorAll("[data-theme-toggle]")) {
            button.addEventListener("click", () => {
                preference = (preference || root.dataset.theme) === "light" ? "dark" : "light";
                try { window.localStorage.setItem(key, preference); } catch { /* Memory-only preference. */ }
                apply(true);
            });
        }
    }, { once: true });
    system?.addEventListener("change", () => { if (!preference) apply(true); });
    motion?.addEventListener?.("change", (event) => { if (event.matches) transition?.skipTransition(); });
    window.addEventListener("storage", (event) => {
        if (event.key !== key && event.key !== null) return;
        preference = event.newValue === "light" || event.newValue === "dark" ? event.newValue : null;
        apply(true);
    });
})();
