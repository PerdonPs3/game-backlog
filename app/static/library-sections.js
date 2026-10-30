"use strict";
(() => {
    const navigation = document.querySelector('.library-heading .section-navigation');
    if (!navigation || !document.querySelector('#collection-filters')) return;
    document.addEventListener('collection:updated', () => {
        const home = new URL(window.location.href);
        home.hash = '';
        const source = home.pathname + home.search;
        for (const link of navigation.querySelectorAll('a')) {
            const destination = new URL(link.href, home);
            if (destination.pathname === home.pathname) {
                link.href = home.href;
            } else {
                if (home.search) destination.searchParams.set('from', source);
                else destination.searchParams.delete('from');
                link.href = destination.href;
            }
        }
    });
})();
