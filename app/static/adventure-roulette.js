"use strict";

(() => {
    const roulette = document.querySelector("#adventure-roulette");
    const result = document.querySelector("#adventure-result");
    const track = document.querySelector("#roulette-track");
    const viewport = document.querySelector("#roulette-viewport");
    const dataNode = document.querySelector("#roulette-data");
    if (!roulette || !result || !track || !viewport || !dataNode) return;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    // Progressive enhancement: the server-rendered result is always the fallback.
    if (reducedMotion.matches || typeof track.animate !== "function") return;
    let data;
    try { data = JSON.parse(dataNode.textContent); } catch { return; }
    if (!Array.isArray(data?.games) || !data.games.length) return;
    const winner = data.games.find((game) => game.id === data.winner_id);
    if (!winner) return;
    const skip = document.querySelector("#skip-roulette");
    const status = document.querySelector("#roulette-status");
    const sound = window.createAdventureSound?.(document.querySelector("#roulette-sound"));
    const form = document.querySelector(".adventure-preferences");
    const submit = form?.querySelector("button[type=submit]");
    const wasDisabled = submit?.disabled;
    let animation;
    let finished = false;
    let winningTile;
    // Only the decorative reel is deduplicated, never the server's candidates.
    // Copies of a title on different platforms should not look like new covers.
    const visualKey = (game) => game.title.trim().toLocaleLowerCase();
    const unique = new Map();
    for (const game of data.games) {
        const key = visualKey(game);
        if (!unique.has(key) || game.id === winner.id) unique.set(key, game);
    }
    const pool = [...unique.values()];
    const winnerOffset = pool.findIndex((game) => game.id === winner.id);
    const single = pool.length === 1;
    const winnerIndex = single ? 0 : 36;
    // Decorative jitter only. Leave a margin so the marker clearly stays
    // inside the server-selected winner, never on a neighbouring tile.
    const landingPoint = single ? 0.5 : 0.15 + Math.random() * 0.7;

    function tileFor(game) {
        const tile = document.createElement("div");
        tile.className = "roulette-tile";
        const cover = document.createElement("div");
        cover.className = "roulette-cover";
        const placeholder = document.createElement("span");
        placeholder.textContent = "No cover available";
        cover.append(placeholder);
        if (game.cover_url) {
            const image = document.createElement("img");
            image.alt = "";
            image.referrerPolicy = "no-referrer";
            image.addEventListener("error", () => image.remove(), { once: true });
            image.src = game.cover_url;
            cover.append(image);
        }
        const title = document.createElement("span");
        title.className = "roulette-title";
        title.textContent = game.title;
        tile.append(cover, title);
        return tile;
    }

    function offset() {
        return viewport.clientWidth / 2 - winningTile.offsetLeft - winningTile.offsetWidth * landingPoint;
    }
    function finish() {
        if (finished) return;
        finished = true;
        animation?.cancel();
        sound?.reveal();
        track.style.transform = `translateX(${offset()}px)`;
        winningTile.classList.add("is-winner");
        roulette.classList.add("is-complete");
        status.textContent = data.candidate_count === 1 ? "One match. One adventure." : "Your next adventure is ready.";
        skip.hidden = true;
        result.hidden = false;
        if (submit) submit.disabled = wasDisabled;
        result.focus({ preventScroll: true });
        window.removeEventListener("resize", finish);
        document.removeEventListener("visibilitychange", onVisibility);
        reducedMotion.removeEventListener("change", onPreference);
    }
    function onVisibility() { if (document.hidden) finish(); }
    function onPreference(event) { if (event.matches) finish(); }

    try {
        for (let index = 0; index < (single ? 1 : 45); index += 1) {
            // Rotate the whole sequence around the already-chosen winner instead
            // of overwriting one slot, which could create identical neighbours.
            const position = ((index - winnerIndex + winnerOffset) % pool.length + pool.length) % pool.length;
            const tile = tileFor(pool[position]);
            track.append(tile);
            if (index === winnerIndex) winningTile = tile;
        }
        roulette.hidden = false;
        result.hidden = true;
        if (submit) submit.disabled = true;
        track.style.paddingLeft = `${Math.max(0, viewport.clientWidth / 2 - winningTile.offsetWidth / 2)}px`;
        skip.addEventListener("click", finish);
        form?.addEventListener("submit", (event) => { if (!finished) event.preventDefault(); });
        window.addEventListener("resize", finish);
        document.addEventListener("visibilitychange", onVisibility);
        reducedMotion.addEventListener("change", onPreference);
        animation = track.animate(single ? [{ opacity: 0.3 }, { opacity: 1 }] : [
            { transform: "translateX(0px)" },
            { transform: `translateX(${offset()}px)` },
        ], {
            duration: single ? 600 : 3000,
            easing: "cubic-bezier(0.12, 0.65, 0.15, 1)", fill: "forwards",
        });
        animation.finished.then(finish, finish);
        if (!single) {
            const stride = track.children[1].offsetLeft - track.children[0].offsetLeft;
            sound?.begin(() => {
                const centre = viewport.getBoundingClientRect().left + viewport.clientWidth / 2;
                return (centre - track.getBoundingClientRect().left - parseFloat(track.style.paddingLeft)) / stride;
            });
        }
    } catch {
        roulette.hidden = true;
        result.hidden = false;
        if (submit) submit.disabled = wasDisabled;
        finished = true;
        animation?.cancel();
        sound?.stop();
    }
})();
