(() => {
    'use strict';
    const sidebar = document.querySelector('.catalog-game-sidebar');
    if (!sidebar) return;
    const header = document.querySelector('.workspace-site-header');
    function update() {
        const top = (header?.getBoundingClientRect().height || 0) + 16;
        const fits = window.innerWidth > 1000 && sidebar.getBoundingClientRect().height <= window.innerHeight - top - 16;
        sidebar.style.setProperty('--catalog-sidebar-top', `${top}px`);
        sidebar.dataset.sticky = String(fits);
    }
    if (typeof ResizeObserver !== 'undefined') {
        const observer = new ResizeObserver(update);
        observer.observe(sidebar);
        if (header) observer.observe(header);
    }
    window.addEventListener('resize', update);
    window.addEventListener('pageshow', update);
    document.fonts?.ready.then(update);
    update();
})();
