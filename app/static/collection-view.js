"use strict";

(() => {
    const controls = document.querySelector("#collection-view-switch");
    const collection = document.querySelector("#game-collection");
    if (!controls || !collection) return;
    const buttons = controls.querySelectorAll("[data-collection-view]");
    const key = "game-backlog.collection-view";

    function apply(view) {
        const selected = view === "shelf" ? "shelf" : "cards";
        collection.dataset.view = selected;
        for (const button of buttons) {
            button.setAttribute("aria-pressed", String(button.dataset.collectionView === selected));
        }
    }

    let saved;
    try { saved = window.localStorage.getItem(key); } catch { /* Storage can be blocked. */ }
    apply(saved);
    controls.hidden = false;
    for (const button of buttons) {
        button.addEventListener("click", () => {
            apply(button.dataset.collectionView);
            try { window.localStorage.setItem(key, collection.dataset.view); } catch { /* Switching still works. */ }
        });
    }
    // Live filters replace only the children, so the selected layout stays intact.
})();
