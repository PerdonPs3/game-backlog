(() => {
    const link = document.querySelector('.welcome-primary');
    if (!link) return;
    let pending = null;
    link.addEventListener('click', (event) => {
        if (event.defaultPrevented || event.button !== 0 || event.ctrlKey ||
            event.metaKey || event.shiftKey || event.altKey ||
            link.hasAttribute('download') || (link.target && link.target !== '_self') ||
            window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
        event.preventDefault();
        if (pending !== null) return;
        document.body.classList.add('is-leaving');
        pending = window.setTimeout(() => window.location.assign(link.href), 230);
    });
    // Back/forward cache can restore the page after its fade-out.
    window.addEventListener('pageshow', () => {
        window.clearTimeout(pending);
        pending = null;
        document.body.classList.remove('is-leaving');
    });
})();
