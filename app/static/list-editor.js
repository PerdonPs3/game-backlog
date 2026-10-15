"use strict";

(() => {
    document.querySelectorAll(".list-preview-cover img, .list-game-choice img").forEach((image) => {
        image.addEventListener("error", () => image.remove(), { once: true });
        if (image.complete && !image.naturalWidth) image.remove();
    });
    const toolbar = document.querySelector("#list-editor-toolbar");
    if (!toolbar) return;
    const rows = [...document.querySelectorAll(".list-game-choice")];
    const buttons = toolbar.querySelectorAll("[data-list-view]");
    const input = document.querySelector("#list-editor-view");
    const count = document.querySelector("#list-selected-count");
    const empty = document.querySelector("#list-selection-empty");
    let view = input.value === "selected" ? "selected" : "all";
    function update() {
        let selected = 0;
        for (const row of rows) {
            const checked = row.querySelector("input[type=checkbox]").checked;
            if (checked) selected++;
            // Hide only: never disable or remove checked inputs from submission.
            row.hidden = view === "selected" && !checked;
        }
        count.textContent = `${selected} ${selected === 1 ? "entry" : "entries"} selected`;
        empty.hidden = view !== "selected" || selected > 0;
        input.value = view;
        for (const button of buttons) {
            button.setAttribute("aria-pressed", String(button.dataset.listView === view));
        }
    }
    for (const button of buttons) button.addEventListener("click", () => {
        view = button.dataset.listView;
        update();
    });
    for (const row of rows) row.querySelector("input[type=checkbox]").addEventListener("change", update);
    toolbar.hidden = false;
    update();
})();
