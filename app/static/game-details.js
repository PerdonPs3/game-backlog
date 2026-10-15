"use strict";

(() => {
    const dialog = document.querySelector("#game-details-dialog");
    if (!dialog || typeof dialog.showModal !== "function") return;
    const content = document.querySelector("#game-details-content");
    const close = document.querySelector("#close-game-details");
    let controller;
    let revision = 0;
    let opener;

    document.addEventListener("click", async (event) => {
        const link = event.target.closest("a[data-game-details]");
        if (!link || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
        if (dialog.open) return;
        event.preventDefault();
        opener = link;
        const current = ++revision;
        controller = new AbortController();
        content.textContent = "Loading game details…";
        content.setAttribute("aria-busy", "true");
        dialog.showModal();
        close.focus();
        try {
            const response = await fetch(link.href, {
                headers: { Accept: "application/json" }, signal: controller.signal,
            });
            if (!response.ok) throw new Error("Unavailable");
            const result = await response.json();
            if (typeof result.html !== "string") throw new Error("Invalid response");
            if (current !== revision || !dialog.open) return;
            // Only this same-origin endpoint's Jinja-escaped fragment is inserted.
            content.innerHTML = result.html;
            const image = content.querySelector(".profile-cover img");
            if (image) {
                const fallback = () => {
                    const placeholder = document.createElement("span");
                    placeholder.textContent = "No cover available";
                    image.replaceWith(placeholder);
                };
                image.addEventListener("error", fallback, { once: true });
                if (image.complete && !image.naturalWidth) fallback();
            }
        } catch (error) {
            if (current !== revision || error.name === "AbortError") return;
            content.textContent = "Could not load this game. Close and try again, or ";
            const fallback = document.createElement("a");
            fallback.href = link.href;
            fallback.textContent = "open its details page";
            content.append(fallback);
        } finally {
            if (current === revision) content.setAttribute("aria-busy", "false");
        }
    });
    close.addEventListener("click", () => dialog.close());
    dialog.addEventListener("close", () => {
        ++revision;
        controller?.abort();
        content.textContent = "";
        content.setAttribute("aria-busy", "false");
        if (opener?.isConnected) opener.focus();
    });
})();
