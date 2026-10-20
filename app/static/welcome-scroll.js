"use strict";
(() => {
    const hero = document.querySelector(".welcome-hero");
    const story = document.querySelector(".welcome-story");
    if (!hero || !story) return;
    const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    let moving = false, timer, intent = 0, touch = null;
    const interactive = (target) => target.closest("input, textarea, select, [role='listbox'], [contenteditable='true'], .catalog-public-search");
    const onCover = () => hero.getBoundingClientRect().bottom > window.innerHeight * .5;
    const nearCover = () => {
        const bottom = hero.getBoundingClientRect().bottom;
        return bottom >= -Math.min(120, window.innerHeight * .15) && bottom < window.innerHeight - 1;
    };
    const destination = (direction) => direction > 0 ? (onCover() ? story : null) : (nearCover() ? hero : null);
    function moveTo(section) {
        moving = true;
        intent = 0;
        section.scrollIntoView({ behavior: "smooth", block: "start" });
        window.clearTimeout(timer);
        timer = window.setTimeout(() => { moving = false; }, 800);
    }
    window.addEventListener("wheel", (event) => {
        if (motion.matches || event.defaultPrevented || event.ctrlKey || interactive(event.target)) return;
        if (!event.deltaY) return;
        if (moving) { event.preventDefault(); return; }
        const section = destination(event.deltaY);
        if (!section) { intent = 0; return; }
        if (Math.sign(intent) !== Math.sign(event.deltaY)) intent = 0;
        intent += event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? window.innerHeight : 1);
        if (Math.abs(intent) >= 24) { event.preventDefault(); moveTo(section); }
    }, { passive: false });
    document.addEventListener("keydown", (event) => {
        if (motion.matches || event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey || (event.shiftKey && event.key !== " ") || interactive(event.target) || event.target.closest("button, a")) return;
        const direction = ["PageUp", "ArrowUp"].includes(event.key) || (event.key === " " && event.shiftKey) ? -1 : ["PageDown", " ", "ArrowDown"].includes(event.key) ? 1 : 0;
        if (!direction) return;
        const section = destination(direction);
        if (moving || section) {
            event.preventDefault();
            if (!moving) moveTo(section);
        }
    });
    document.addEventListener("touchstart", (event) => {
        touch = !interactive(event.target) && event.touches.length === 1 ? { x: event.touches[0].clientX, y: event.touches[0].clientY } : null;
    }, { passive: true });
    document.addEventListener("touchend", (event) => {
        if (!touch || motion.matches || moving || !event.changedTouches.length) { touch = null; return; }
        const dy = touch.y - event.changedTouches[0].clientY;
        const dx = touch.x - event.changedTouches[0].clientX;
        touch = null;
        const section = destination(dy);
        if (Math.abs(dy) > 45 && Math.abs(dy) > Math.abs(dx) && section) moveTo(section);
    }, { passive: true });
    window.addEventListener("pageshow", () => { window.clearTimeout(timer); moving = false; intent = 0; touch = null; });
})();
