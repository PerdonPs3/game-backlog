/* Each chapter stays visible without JavaScript; motion adds progressive decoration. */
(() => {
    const chapters = document.querySelectorAll('[data-tour-panel]');
    if (!('IntersectionObserver' in window)) return;
    const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
    const observer = new window.IntersectionObserver(entries => {
        entries.forEach(entry => {
            if (!entry.isIntersecting) return;
            entry.target.classList.add('is-revealed');
            observer.unobserve(entry.target);
        });
    }, { threshold: .12 });
    const update = () => {
        if (motion.matches) {
            observer.disconnect();
            chapters.forEach(chapter => chapter.classList.add('is-revealed'));
        } else chapters.forEach(chapter => {
            if (!chapter.classList.contains('is-revealed')) observer.observe(chapter);
        });
    };
    motion.addEventListener('change', update);
    window.addEventListener('pagehide', () => observer.disconnect());
    window.addEventListener('pageshow', update);
    update();
})();
