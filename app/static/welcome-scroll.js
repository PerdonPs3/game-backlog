"use strict";
(() => {
    const hero = document.querySelector(".welcome-hero");
    const story = document.querySelector(".welcome-story");
    if (!hero || !story) return;
    const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    let moving = false, timer, intent = 0, touch = null;
    const interactive = (target) => target.closest("input, textarea, select, [role='listbox'], [contenteditable='true'], .catalog-public-search");
    const onCover = () => hero.getBoundingClientRect().bottom > window.innerHeight * .5;
    function advance() {
        moving = true;
        intent = 0;
        story.scrollIntoView({ behavior: "smooth", block: "start" });
        window.clearTimeout(timer);
        timer = window.setTimeout(() => { moving = false; }, 800);
    }
    window.addEventListener("wheel", (event) => {
        if (motion.matches || event.defaultPrevented || event.ctrlKey || interactive(event.target)) return;
        if (event.deltaY <= 0) { intent = 0; moving = false; return; }
        if (moving) { event.preventDefault(); return; }
        if (!onCover()) return;
        intent += event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? window.innerHeight : 1);
        if (intent >= 24) { event.preventDefault(); advance(); }
    }, { passive: false });
    document.addEventListener("keydown", (event) => {
        if (motion.matches || event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey || event.shiftKey || interactive(event.target) || event.target.closest("button, a")) return;
        if (["PageDown", " ", "ArrowDown"].includes(event.key) && onCover()) {
            event.preventDefault();
            if (!moving) advance();
        }
    });
    document.addEventListener("touchstart", (event) => {
        touch = !interactive(event.target) && event.touches.length === 1 ? { x: event.touches[0].clientX, y: event.touches[0].clientY } : null;
    }, { passive: true });
    document.addEventListener("touchend", (event) => {
        if (!touch || motion.matches || moving || !onCover() || !event.changedTouches.length) { touch = null; return; }
        const dy = touch.y - event.changedTouches[0].clientY;
        const dx = touch.x - event.changedTouches[0].clientX;
        touch = null;
        if (dy > 45 && dy > Math.abs(dx)) advance();
    }, { passive: true });
    window.addEventListener("pageshow", () => { window.clearTimeout(timer); moving = false; intent = 0; touch = null; });
})();
