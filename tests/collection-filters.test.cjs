const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const { runInNewContext } = require("node:vm");

class Element {
    constructor() { this.value = ""; this.listeners = {}; this.attributes = {}; this.children = []; }
    addEventListener(name, callback) { this.listeners[name] = callback; }
    fire(name, extra = {}) { return this.listeners[name]?.({ preventDefault() {}, ...extra }); }
    setAttribute(name, value) { this.attributes[name] = value; }
    replaceChildren() { this.children = []; }
    append(node) { this.children.push(node); }
}

function setup() {
    const ids = ["collection-filters", "title-search", "status-filter", "apply-filters",
                 "filter-reset", "game-collection", "filter-message", "collection-sort"];
    const nodes = Object.fromEntries(ids.map((id) => [id, new Element()]));
    const form = nodes["collection-filters"];
    form.action = "http://localhost/";
    nodes["collection-sort"].value = "newest";
    form.querySelector = (selector) => nodes[selector.slice(1)];
    const document = new Element();
    document.querySelector = form.querySelector;
    document.createElement = () => new Element();
    const events = [];
    document.dispatchEvent = (event) => events.push(event.type);
    const requests = [];
    const history = [];
    const timers = new Map();
    let nextTimer = 0;
    runInNewContext(readFileSync(join(__dirname, "../app/static/collection-filters.js"), "utf8"), {
        document, URL, AbortController, Event: class { constructor(type) { this.type = type; } },
        window: { location: { href: "http://localhost/" }, history: {
            replaceState(state, title, url) { history.push(String(url)); },
        } },
        setTimeout(callback) { const id = ++nextTimer; timers.set(id, callback); return id; },
        clearTimeout(id) { timers.delete(id); },
        fetch(url, options) {
            return new Promise((resolve) => requests.push({ url: String(url), options,
                reply(html, count, ok = true) { resolve({ ok, json: async () => ({ html, count }) }); },
            }));
        },
    });
    return { ...nodes, requests, events, history, timers,
        run() { const [id, callback] = [...timers.entries()].at(-1); timers.delete(id); return callback(); },
    };
}

test("typing is debounced and combines title and status without reloading inputs", async () => {
    const ui = setup();
    for (const value of ["r", "re", "res"]) {
        ui["title-search"].value = value;
        ui["title-search"].fire("input");
    }
    assert.equal(ui.requests.length, 0);
    assert.equal(ui.timers.size, 1);
    ui["status-filter"].value = "Completed";
    ui["status-filter"].fire("change");
    const pending = ui.run();
    assert.equal(ui.requests[0].url, "http://localhost/?q=res&status=Completed");
    ui.requests[0].reply("<article>Resident</article>", 1);
    await pending;
    assert.equal(ui["game-collection"].innerHTML, "<article>Resident</article>");
    assert.equal(ui["title-search"].value, "res");
    assert.equal(ui["filter-message"].textContent, "1 game found.");
    assert.equal(ui["filter-reset"].hidden, false);
    assert.equal(ui["game-collection"].attributes["aria-busy"], "false");
    assert.equal(ui.events[0], "collection:updated");
    assert.equal(ui.history[0], ui.requests[0].url);
});

test("older responses never replace the newest search", async () => {
    const ui = setup();
    ui["title-search"].value = "res";
    ui["title-search"].fire("input");
    const older = ui.run();
    ui["title-search"].value = "portal";
    ui["title-search"].fire("input");
    assert.equal(ui.requests[0].options.signal.aborted, true);
    const newer = ui.run();
    ui.requests[1].reply("Portal", 1);
    await newer;
    ui.requests[0].reply("Resident", 2);
    await older;
    assert.equal(ui["game-collection"].innerHTML, "Portal");
    assert.equal(ui.history.length, 1);
});

test("clearing filters requests all games", async () => {
    const ui = setup();
    ui["title-search"].value = "res";
    ui["status-filter"].value = "Playing";
    ui["filter-reset"].fire("click", { target: { closest: () => ({}) } });
    const pending = ui.run();
    assert.equal(ui.requests[0].url, "http://localhost/");
    ui.requests[0].reply("All games", 3);
    await pending;
    assert.equal(ui["filter-reset"].children.length, 0);
    assert.equal(ui["filter-reset"].hidden, true);
    assert.equal(ui["title-search"].value, "");
    assert.equal(ui["status-filter"].value, "");
});

test("failed requests preserve current cards and expose a retry", async () => {
    const ui = setup();
    ui["game-collection"].innerHTML = "Previous results";
    ui["collection-filters"].fire("submit");
    const pending = ui.run();
    ui.requests[0].reply("", 0, false);
    await pending;
    assert.equal(ui["game-collection"].innerHTML, "Previous results");
    assert.equal(ui["apply-filters"].hidden, false);
    assert.equal(ui.history.length, 0);
    assert.equal(ui["game-collection"].attributes["aria-busy"], "false");
});

test("IME input waits for composition to finish", async () => {
    const ui = setup();
    ui["title-search"].fire("compositionstart");
    ui["title-search"].value = "ゲーム";
    ui["title-search"].fire("input");
    assert.equal(ui.timers.size, 0);
    ui["title-search"].fire("compositionend");
    const pending = ui.run();
    ui.requests[0].reply("Games", 1);
    await pending;
    assert.equal(ui.requests.length, 1);
});

test("cover fallbacks are reattached after filtering", () => {
    let images = [];
    const document = new Element();
    document.querySelectorAll = () => images;
    runInNewContext(readFileSync(join(__dirname, "../app/static/collection-covers.js"), "utf8"), { document });
    const image = new Element();
    image.dataset = {};
    image.complete = false;
    image.remove = () => { image.removed = true; };
    images = [image];
    document.fire("collection:updated");
    image.fire("error");
    assert.equal(image.removed, true);
});

test("changing sort refreshes results and keeps it when clearing filters", async () => {
    const ui = setup();
    ui["title-search"].value = "res";
    ui["collection-sort"].value = "rating";
    ui["collection-sort"].fire("change");
    let pending = ui.run();
    assert.equal(ui.requests[0].url, "http://localhost/?q=res&sort=rating");
    ui.requests[0].reply("Highest rated first", 2);
    await pending;
    assert.equal(ui["filter-reset"].children[0].href, "http://localhost/?sort=rating");
    ui["filter-reset"].fire("click", { target: { closest: () => ({}) } });
    pending = ui.run();
    assert.equal(ui.requests[1].url, "http://localhost/?sort=rating");
    ui.requests[1].reply("All games sorted", 3);
    await pending;
    assert.equal(ui["collection-sort"].value, "rating");
    assert.equal(ui["game-collection"].innerHTML, "All games sorted");
});

test("stale sorting response cannot overwrite a newer ordering", async () => {
    const ui = setup();
    ui["collection-sort"].value = "rating";
    ui["collection-sort"].fire("change");
    const old = ui.run();
    ui["collection-sort"].value = "title";
    ui["collection-sort"].fire("change");
    const newer = ui.run();
    ui.requests[1].reply("Alphabetical", 3);
    await newer;
    ui.requests[0].reply("Highest rated", 3);
    await old;
    assert.equal(ui["game-collection"].innerHTML, "Alphabetical");
    assert.equal(ui.history[0], "http://localhost/?sort=title");
});
