/* The preview remains readable as stacked sections when JavaScript is unavailable. */
(() => {
    document.querySelectorAll('[data-product-tour]').forEach(tour => {
        const navigation = tour.querySelector('[role="tablist"]');
        const tabs = Array.from(navigation.querySelectorAll('[role="tab"]'));
        const panels = Array.from(tour.querySelectorAll('[data-tour-panel]'));
        const select = (index, focus = false) => {
            tabs.forEach((tab, position) => {
                const active = position === index;
                tab.setAttribute('aria-selected', String(active));
                tab.tabIndex = active ? 0 : -1;
                panels[position].hidden = !active;
            });
            if (focus) tabs[index].focus();
        };
        tabs.forEach((tab, index) => {
            panels[index].setAttribute('role', 'tabpanel');
            panels[index].setAttribute('aria-labelledby', tab.id);
            tab.addEventListener('click', () => select(index));
            tab.addEventListener('keydown', event => {
                let next;
                if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
                if (event.key === 'ArrowLeft') next = (index - 1 + tabs.length) % tabs.length;
                if (event.key === 'Home') next = 0;
                if (event.key === 'End') next = tabs.length - 1;
                if (next !== undefined) { event.preventDefault(); select(next, true); }
            });
        });
        select(0);
        navigation.hidden = false;
    });
})();
