"use strict";

(() => {
    const mouse = window.matchMedia("(hover: hover) and (pointer: fine)");
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    const logo = document.querySelector("[data-easter-egg-logo]");
    const glow = document.createElement("div");
    glow.className = "cursor-glow";
    glow.setAttribute("aria-hidden", "true");
    document.body.append(glow);
    let frame = null;
    let x = 0;
    let y = 0;

    function hide() {
        if (frame !== null) window.cancelAnimationFrame(frame);
        frame = null;
        glow.classList.remove("is-visible");
        logo?.style.setProperty("--logo-light", "0");
    }

    document.addEventListener("pointermove", (event) => {
        if (!mouse.matches || reducedMotion.matches || event.pointerType !== "mouse") {
            hide();
            return;
        }
        x = event.clientX;
        y = event.clientY;
        if (frame !== null) return;
        frame = window.requestAnimationFrame(() => {
            if (logo) {
                const bounds = logo.getBoundingClientRect();
                const dx = Math.max(bounds.left - x, 0, x - bounds.right);
                const dy = Math.max(bounds.top - y, 0, y - bounds.bottom);
                const proximity = Math.max(0, 1 - Math.hypot(dx, dy) / 240);
                logo.style.setProperty("--logo-light", String(proximity ** 2));
            }
            glow.style.transform = `translate3d(${x - 280}px, ${y - 280}px, 0)`;
            glow.classList.add("is-visible");
            frame = null;
        });
    }, { passive: true });

    document.addEventListener("pointerleave", hide);
    document.addEventListener("visibilitychange", () => {
        if (document.hidden) hide();
    });
    window.addEventListener("blur", hide);
    mouse.addEventListener("change", hide);
    reducedMotion.addEventListener("change", hide);
})();
