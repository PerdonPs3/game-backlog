"use strict";

(() => {
    const dialog = document.querySelector("#delete-game-dialog");
    if (!dialog || typeof dialog.showModal !== "function") return;
    const form = dialog.querySelector("#delete-game-form");
    const title = dialog.querySelector("#delete-game-title");
    const cancel = dialog.querySelector("#cancel-delete");
    const confirm = dialog.querySelector("#confirm-delete");
    let opener;
    let submitting = false;

    // Delegation also handles cards replaced by live filtering.
    document.addEventListener("click", (event) => {
        const link = event.target.closest("a[data-delete-game]");
        if (!link || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
        if (!link.closest("#game-collection")) return;
        event.preventDefault();
        if (dialog.open) return;
        opener = link;
        form.action = link.href;
        title.textContent = link.dataset.gameTitle;
        submitting = false;
        confirm.disabled = false;
        confirm.textContent = "Yes, delete game";
        cancel.disabled = false;
        dialog.showModal();
        cancel.focus();
    });

    cancel.addEventListener("click", () => {
        if (!submitting) dialog.close();
    });
    dialog.addEventListener("cancel", (event) => {
        if (submitting) event.preventDefault();
    });
    dialog.addEventListener("close", () => {
        confirm.disabled = true;
        form.removeAttribute("action");
        title.textContent = "";
        if (opener?.isConnected) opener.focus();
    });
    form.addEventListener("submit", (event) => {
        if (submitting || !dialog.open || !form.hasAttribute("action")) {
            event.preventDefault();
            return;
        }
        submitting = true;
        confirm.disabled = true;
        confirm.textContent = "Deleting...";
        cancel.disabled = true;
        // Native POST retains CSRF protection and the server's redirect.
    });
})();
