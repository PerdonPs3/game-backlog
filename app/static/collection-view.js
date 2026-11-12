"use strict";

(() => {
    const controls = document.querySelector("#collection-view-switch");
    const collection = document.querySelector("#game-collection");
    if (!controls || (!collection && !controls.dataset?.libraryUrl)) return;
    const buttons = controls.querySelectorAll("[data-collection-view]");
    const key = "game-backlog.collection-view";

    function apply(view) {
        const selected = view === "shelf" ? "shelf" : "cards";
        if (collection) collection.dataset.view = selected;
        for (const button of buttons) {
            button.setAttribute("aria-pressed", String(button.dataset.collectionView === selected));
        }
    }

    let saved;
    try { saved = window.localStorage.getItem(key); } catch { /* Storage can be blocked. */ }
    const requested = new URL(window.location.href).searchParams.get('view');
    apply(requested === 'cards' || requested === 'shelf' ? requested : saved);
    controls.hidden = false;
    for (const button of buttons) {
        button.addEventListener("click", () => {
            apply(button.dataset.collectionView);
            try { window.localStorage.setItem(key, button.dataset.collectionView); } catch { /* Switching still works. */ }
            if (collection && requested !== null) {
                const current = new URL(window.location.href);
                current.searchParams.set('view', button.dataset.collectionView);
                window.history.replaceState(null, '', current);
            }
            if (!collection) {
                const destination = new URL(controls.dataset.libraryUrl, window.location.href);
                destination.searchParams.set('view', button.dataset.collectionView);
                window.location.assign(destination.href);
            }
        });
    }
    // Live filters replace only the children, so the selected layout stays intact.
})();
