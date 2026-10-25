"use strict";

(() => {
    const form = document.querySelector("#collection-filters");
    if (!form) return;
    const search = form.querySelector("#title-search");
    const status = form.querySelector("#status-filter");
    const sort = form.querySelector("#collection-sort");
    const list = form.querySelector("#list-filter");
    const button = form.querySelector("#apply-filters");
    const reset = form.querySelector("#filter-reset");
    const collection = document.querySelector("#game-collection");
    const message = document.querySelector("#filter-message");
    const counter = document.querySelector("#collection-count");
    let timer;
    let controller;
    let revision = 0;
    let composing = false;

    button.hidden = true;

    function schedule(delay = 250) {
        clearTimeout(timer);
        controller?.abort();
        const currentRevision = ++revision;
        collection.setAttribute("aria-busy", "true");
        message.textContent = "Updating your collection...";
        timer = setTimeout(() => updateCollection(currentRevision), delay);
    }

    async function updateCollection(currentRevision) {
        const url = new URL(form.action, window.location.href);
        const query = search.value.trim();
        if (query) url.searchParams.set("q", query);
        if (status.value) url.searchParams.set("status", status.value);
        if (sort.value !== "newest") url.searchParams.set("sort", sort.value);
        if (list?.value) url.searchParams.set("list", list.value);
        controller = new AbortController();
        try {
            const response = await fetch(url, {
                signal: controller.signal,
                headers: { Accept: "application/json" },
            });
            if (!response.ok) throw new Error("Filter request failed.");
            const data = await response.json();
            if (currentRevision !== revision) return;
            if (typeof data.html !== "string" || !Number.isInteger(data.count) || data.count < 0 ||
                !Number.isInteger(data.total) || data.total < data.count) {
                throw new Error("Invalid collection response.");
            }
            // Only the server-rendered, autoescaped collection fragment is inserted.
            collection.innerHTML = data.html;
            reset.replaceChildren();
            reset.hidden = !query && !status.value && !list?.value;
            if (query || status.value || list?.value) {
                const link = document.createElement("a");
                const resetUrl = new URL(form.action, window.location.href);
                if (sort.value !== "newest") resetUrl.searchParams.set("sort", sort.value);
                link.href = resetUrl.href;
                link.textContent = "Clear filters";
                reset.append(link);
            }
            window.history.replaceState(null, "", url);
            document.dispatchEvent(new Event("collection:updated"));
            if (counter) {
                counter.textContent = query || status.value || list?.value
                    ? `${data.count} of ${data.total} ${data.total === 1 ? "game" : "games"}`
                    : `${data.total} ${data.total === 1 ? "game" : "games"}`;
                message.textContent = "";
            } else {
                message.textContent = `${data.count} ${data.count === 1 ? "game" : "games"} found.`;
            }
            button.hidden = true;
        } catch (error) {
            if (currentRevision !== revision || error.name === "AbortError") return;
            message.textContent = "Could not update the collection. Previous results are still shown. Try Apply filters again.";
            button.hidden = false;
        } finally {
            if (currentRevision === revision) collection.setAttribute("aria-busy", "false");
        }
    }

    search.addEventListener("input", () => {
        if (!composing) schedule();
    });
    search.addEventListener("compositionstart", () => {
        composing = true;
        clearTimeout(timer);
        controller?.abort();
        revision += 1;
        collection.setAttribute("aria-busy", "false");
    });
    search.addEventListener("compositionend", () => {
        composing = false;
        schedule();
    });
    status.addEventListener("change", () => schedule(0));
    sort.addEventListener("change", () => schedule(0));
    list?.addEventListener("change", () => schedule(0));
    form.addEventListener("submit", (event) => {
        event.preventDefault();
        schedule(0);
    });
    reset.addEventListener("click", (event) => {
        if (!event.target.closest("a")) return;
        event.preventDefault();
        search.value = "";
        status.value = "";
        if (list) list.value = "";
        schedule(0);
    });
})();
