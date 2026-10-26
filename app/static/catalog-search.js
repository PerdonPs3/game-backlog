"use strict";

(() => {
    const picker = document.querySelector("[data-catalog-url]");
    if (!picker) return;

    const browsing = Boolean(picker.dataset.browseUrl);
    const input = picker.querySelector(browsing ? "#catalog-query" : "#title");
    const results = picker.querySelector("#catalog-results");
    const message = picker.querySelector("#catalog-message");
    const content = picker.querySelector("[data-catalog-content]");
    const platform = document.querySelector("#platform");
    const gameId = document.querySelector("#igdb-id");
    const submit = document.querySelector("#add-game-button");
    const platformMessage = document.querySelector("#platform-message");
    const preview = document.querySelector("[data-entry-preview]");
    const selectionPanel = document.querySelector("[data-entry-catalog]");
    let timer;
    let controller;
    let revision = 0;
    let matches = [];
    let active = -1;
    let loadingDetails = false;

    function showSelection(selected) {
        if (!preview) return;
        preview.hidden = !selected;
        if (!selected) return;
        preview.querySelector("[data-entry-title]").textContent = selected.name;
        preview.querySelector("[data-entry-year]").textContent = selected.year || "";
        const cover = preview.querySelector("[data-entry-cover]");
        const placeholder = document.createElement("span");
        placeholder.textContent = "No cover";
        cover.replaceChildren(placeholder);
        if (selected.cover_url) {
            const image = document.createElement("img");
            image.src = selected.cover_url.replace("/t_cover_small/", "/t_cover_big/");
            image.alt = "";
            image.referrerPolicy = "no-referrer";
            image.addEventListener("error", () => image.remove());
            cover.append(image);
        }
        if (selectionPanel) {
            selectionPanel.open = false;
            selectionPanel.querySelector("[data-entry-catalog-label]").textContent = "Change game";
            platform.focus();
        }
    }

    function resetSelection(label = "Choose a game first") {
        showSelection(null);
        gameId.value = "";
        platform.replaceChildren(new Option(label, ""));
        platform.disabled = true;
        submit.disabled = true;
        input.setCustomValidity("Choose a game from the catalog suggestions.");
        platformMessage.textContent = "";
    }

    if (!browsing) {
        platform.addEventListener("change", () => {
            submit.disabled = !gameId.value || !platform.value;
        });
        submit.disabled = !gameId.value || !platform.value;
        if (!gameId.value) input.setCustomValidity("Choose a game from the catalog suggestions.");
    }

    function closeResults() {
        results.hidden = true;
        input.setAttribute("aria-expanded", "false");
        input.removeAttribute("aria-activedescendant");
        active = -1;
    }

    async function selectGame(game) {
        if (browsing) {
            clearTimeout(timer);
            controller?.abort();
            revision += 1;
            closeResults();
            const url = picker.dataset.browseUrl.replace(/0$/, String(game.id));
            if (!window.VestigiumCatalogNavigation?.go(url)) window.location.assign(url);
            return;
        }
        clearTimeout(timer);
        controller?.abort();
        const currentRevision = ++revision;
        resetSelection("Loading available platforms...");
        loadingDetails = true;
        input.value = game.name;
        message.textContent = "Checking available platforms...";
        closeResults();
        input.focus();
        controller = new AbortController();
        try {
            const url = picker.dataset.detailsUrl.replace(/0$/, String(game.id));
            const response = await fetch(url, {
                signal: controller.signal,
                headers: { Accept: "application/json" },
            });
            const data = await response.json();
            if (currentRevision !== revision) return;
            if (!response.ok) throw new Error("Could not check the selected game.");
            const selected = data.game;
            input.value = selected.name;
            platform.replaceChildren(new Option("Choose a platform", ""));
            selected.platforms.forEach((name) => platform.add(new Option(name, name)));
            if (!selected.platforms.length) {
                resetSelection("No platforms available");
                message.textContent = "This game has no platforms listed in IGDB. Please choose another game.";
                return;
            }
            gameId.value = String(selected.id);
            input.setCustomValidity("");
            platform.disabled = false;
            message.textContent = `Selected: ${selected.name}${selected.year ? ` (${selected.year})` : ""}.`;
            platformMessage.textContent = "";
            showSelection(selected);
        } catch (error) {
            if (currentRevision !== revision || error.name === "AbortError") return;
            resetSelection();
            message.textContent = "Could not check platforms. Search and select the game again to retry.";
        } finally {
            if (currentRevision === revision) loadingDetails = false;
        }
    }

    function showResults(games) {
        matches = games;
        results.replaceChildren();
        active = -1;
        input.removeAttribute("aria-activedescendant");
        if (!games.length) {
            closeResults();
            message.textContent = browsing ? "No matching games." : "No matching games found. Try a longer title.";
            return;
        }

        games.forEach((game, index) => {
            const option = document.createElement("button");
            option.type = "button";
            option.className = "catalog-option";
            option.id = `catalog-option-${index}`;
            option.tabIndex = -1;
            option.setAttribute("role", "option");
            option.setAttribute("aria-selected", "false");

            const cover = document.createElement("span");
            cover.className = "catalog-cover";
            cover.textContent = "No cover";
            if (game.cover_url) {
                const image = document.createElement("img");
                image.src = game.cover_url;
                image.alt = "";
                image.loading = "lazy";
                image.referrerPolicy = "no-referrer";
                image.addEventListener("error", () => image.remove());
                cover.append(image);
            }

            const details = document.createElement("span");
            const title = document.createElement("strong");
            title.textContent = game.name;
            const metadata = document.createElement("span");
            metadata.className = "catalog-metadata";
            metadata.textContent = game.year || "Year unknown";
            details.append(title, metadata);
            option.append(cover, details);
            option.addEventListener("pointerdown", (event) => event.preventDefault());
            option.addEventListener("click", () => selectGame(game));
            results.append(option);
        });
        results.hidden = false;
        input.setAttribute("aria-expanded", "true");
        message.textContent = `${games.length} matches.`;
    }

    function search() {
        clearTimeout(timer);
        controller?.abort();
        const currentRevision = ++revision;
        loadingDetails = false;
        if (!browsing) resetSelection();
        closeResults();
        const term = input.value.trim();
        if (term.length < 2) {
            message.textContent = "";
            return;
        }
        message.textContent = "Searching the catalog...";
        timer = setTimeout(async () => {
            controller = new AbortController();
            try {
                const url = new URL(picker.dataset.catalogUrl, window.location.origin);
                url.searchParams.set("q", term);
                if (content) url.searchParams.set("content", content.value);
                const response = await fetch(url, {
                    signal: controller.signal,
                    headers: { Accept: "application/json" },
                });
                const data = await response.json();
                if (currentRevision !== revision) return;
                if (!response.ok) throw new Error(data.error || "Catalog unavailable.");
                showResults(data.games);
            } catch (error) {
                if (error.name === "AbortError" || currentRevision !== revision) return;
                closeResults();
                message.textContent = "Could not load suggestions. Please try again shortly.";
            }
        }, 450);
    }
    input.addEventListener("input", search);
    content?.addEventListener("change", search);

    input.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            clearTimeout(timer);
            controller?.abort();
            revision += 1;
            if (loadingDetails) resetSelection();
            loadingDetails = false;
            closeResults();
            message.textContent = "Suggestions closed.";
            return;
        }
        if (results.hidden) return;
        if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault();
            const direction = event.key === "ArrowDown" ? 1 : -1;
            active = active < 0
                ? (direction === 1 ? 0 : matches.length - 1)
                : (active + direction + matches.length) % matches.length;
            [...results.children].forEach((option, index) => {
                option.setAttribute("aria-selected", String(index === active));
            });
            const option = results.children[active];
            input.setAttribute("aria-activedescendant", option.id);
            option.scrollIntoView({ block: "nearest" });
        } else if (event.key === "Enter" && active >= 0) {
            event.preventDefault();
            selectGame(matches[active]);
        }
    });

    document.addEventListener("click", (event) => {
        if (!picker.contains(event.target)) {
            clearTimeout(timer);
            if (!loadingDetails) {
                controller?.abort();
                revision += 1;
            }
            closeResults();
        }
    });
    input.addEventListener("blur", () => {
        clearTimeout(timer);
        if (!loadingDetails) {
            controller?.abort();
            revision += 1;
        }
        closeResults();
    });
})();
