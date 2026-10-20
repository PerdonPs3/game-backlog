"use strict";

(() => {
    const badge = document.querySelector("[data-member-count-url]");
    if (!badge) return;
    const value = badge.querySelector("[data-member-count-value]");
    let controller;
    let stopped = false;
    let pending = false;

    async function refresh() {
        if (document.hidden || stopped || pending) return;
        pending = true;
        controller = new AbortController();
        try {
            const response = await fetch(badge.dataset.memberCountUrl, {
                signal: controller.signal, headers: { Accept: "application/json" },
            });
            const data = await response.json();
            if (!response.ok || !Number.isSafeInteger(data.count) || data.count < 0) throw new Error("Unavailable");
            if (stopped) return;
            value.textContent = data.count.toLocaleString("en-US");
            badge.setAttribute("aria-label", `${data.count} activated player ${data.count === 1 ? "account" : "accounts"}`);
            badge.hidden = false;
        } catch (error) {
            if (error.name !== "AbortError") badge.hidden = true;
        } finally {
            pending = false;
        }
    }
    let timer = window.setInterval(refresh, 60000);
    window.addEventListener("pagehide", () => {
        stopped = true;
        controller?.abort();
        window.clearInterval(timer);
    });
    window.addEventListener("pageshow", (event) => {
        if (event.persisted) {
            stopped = false;
            timer = window.setInterval(refresh, 60000);
            refresh();
        }
    });
})();
