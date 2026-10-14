// Small DOM double: test interaction logic without network or browser dependencies.
const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const { runInNewContext } = require("node:vm");

class Element {
    constructor() {
        this.children = [];
        this.listeners = {};
        this.attributes = {};
        this.value = "";
        this.hidden = true;
    }
    addEventListener(name, callback) { this.listeners[name] = callback; }
    fire(name, extra = {}) {
        return this.listeners[name]?.({ preventDefault() {}, ...extra });
    }
    setAttribute(name, value) { this.attributes[name] = value; }
    removeAttribute(name) { delete this.attributes[name]; }
    setCustomValidity(value) { this.validity = value; }
    replaceChildren(...children) { this.children = children; this.value = ""; }
    append(...children) { this.children.push(...children); }
    add(child) { this.append(child); }
    focus() {}
    scrollIntoView() {}
}

function setup() {
    const elements = Object.fromEntries([
        "title", "catalog-results", "catalog-message", "platform", "igdb-id",
        "add-game-button", "platform-message",
    ].map((id) => [`#${id}`, new Element()]));
    const picker = new Element();
    picker.dataset = { catalogUrl: "/catalog/search", detailsUrl: "/catalog/games/0" };
    picker.querySelector = (selector) => elements[selector];
    picker.contains = () => true;
    const document = new Element();
    document.querySelector = (selector) => selector === "[data-catalog-url]" ? picker : elements[selector];
    document.createElement = () => new Element();
    const requests = [];
    let scheduled;
    const context = {
        document, URL, AbortController,
        window: { location: { origin: "http://localhost" } },
        Option: class extends Element {
            constructor(text, value) { super(); this.textContent = text; this.value = value; }
        },
        setTimeout(callback) { scheduled = callback; return 1; },
        clearTimeout() { scheduled = undefined; },
        fetch(url, options) {
            return new Promise((resolve) => requests.push({
                url: String(url), options,
                reply(data, ok = true) { resolve({ ok, json: async () => data }); },
            }));
        },
    };
    runInNewContext(readFileSync(join(__dirname, "../app/static/catalog-search.js"), "utf8"), context);
    return {
        ...Object.fromEntries(Object.entries(elements).map(([key, value]) => [key.slice(1), value])),
        requests,
        async search(games) {
            elements["#title"].value = "Resident";
            elements["#title"].fire("input");
            const pending = scheduled();
            requests.at(-1).reply({ games });
            await pending;
        },
    };
}

const original = { id: 1, name: "Resident Evil", year: 1996, platforms: ["PC", "PlayStation"] };
const remake = { id: 2, name: "Resident Evil", year: 2002, platforms: ["Nintendo GameCube"] };

test("platforms remain locked until a game is resolved, then require a choice", async () => {
    const ui = setup();
    assert.equal(ui["add-game-button"].disabled, true);
    await ui.search([original]);
    const pending = ui["catalog-results"].children[0].fire("click");
    assert.equal(ui.platform.disabled, true);
    assert.equal(ui.requests.at(-1).url, "/catalog/games/1");
    ui.requests.at(-1).reply({ game: original });
    await pending;
    assert.equal(ui.platform.disabled, false);
    assert.equal(ui["igdb-id"].value, "1");
    assert.deepEqual(ui.platform.children.map((o) => o.value), ["", "PC", "PlayStation"]);
    assert.equal(ui["add-game-button"].disabled, true);
    ui.platform.value = "PC";
    ui.platform.fire("change");
    assert.equal(ui["add-game-button"].disabled, false);
    ui.title.value = "Different game";
    ui.title.fire("input");
    assert.equal(ui["igdb-id"].value, "");
    assert.equal(ui.platform.disabled, true);
    assert.equal(ui["add-game-button"].disabled, true);
});

test("stale platform response cannot restore a previous selection", async () => {
    const ui = setup();
    await ui.search([original]);
    const pending = ui["catalog-results"].children[0].fire("click");
    const request = ui.requests.at(-1);
    ui.title.value = "Portal";
    ui.title.fire("input");
    assert.equal(request.options.signal.aborted, true);
    request.reply({ game: original });
    await pending;
    assert.equal(ui.title.value, "Portal");
    assert.equal(ui["igdb-id"].value, "");
    assert.equal(ui.platform.disabled, true);
});

test("ArrowUp starts at the last suggestion", async () => {
    const ui = setup();
    await ui.search([original, remake]);
    ui.title.fire("keydown", { key: "ArrowUp" });
    assert.equal(ui["catalog-results"].children[1].attributes["aria-selected"], "true");
});

test("missing platforms and catalog errors cannot enable saving", async () => {
    for (const ok of [true, false]) {
        const ui = setup();
        await ui.search([original]);
        const pending = ui["catalog-results"].children[0].fire("click");
        ui.requests.at(-1).reply({ game: { ...original, platforms: [] } }, ok);
        await pending;
        assert.equal(ui.platform.disabled, true);
        assert.equal(ui["add-game-button"].disabled, true);
        assert.equal(ui["igdb-id"].value, "");
    }
});

test("moving focus while platforms load does not discard the selection", async () => {
    const ui = setup();
    await ui.search([original]);
    const pending = ui["catalog-results"].children[0].fire("click");
    ui.title.fire("blur");
    assert.equal(ui.requests.at(-1).options.signal.aborted, false);
    ui.requests.at(-1).reply({ game: original });
    await pending;
    assert.equal(ui["igdb-id"].value, "1");
});
