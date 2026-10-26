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
    contains(target) { return target === this || this.children.some(child => child.contains?.(target)); }
    scrollIntoView() {}
}

function setup(browsing = false, withFilter = false, withPreview = false) {
    const elements = Object.fromEntries([
        "title", "catalog-query", "catalog-results", "catalog-message", "platform", "igdb-id",
        "add-game-button", "platform-message",
    ].map((id) => [`#${id}`, new Element()]));
    if (withFilter) {
        elements['[data-catalog-content]'] = new Element();
        elements['[data-catalog-content]'].value = 'official';
    }
    if (withPreview) {
        const previewFields = Object.fromEntries(['[data-entry-title]', '[data-entry-year]', '[data-entry-cover]'].map(key => [key, new Element()]));
        elements['[data-entry-preview]'] = new Element();
        elements['[data-entry-preview]'].querySelector = selector => previewFields[selector];
        elements['[data-entry-catalog]'] = new Element();
        elements['[data-entry-catalog]'].hidden = false;
        elements['[data-entry-change]'] = new Element();
        Object.assign(elements, previewFields);
    }
    const picker = new Element();
    picker.dataset = { catalogUrl: "/catalog/search", detailsUrl: "/catalog/games/0" };
    if (browsing) picker.dataset = { catalogUrl: "/explore/suggestions", browseUrl: "/explore/games/0" };
    picker.querySelector = (selector) => elements[selector];
    picker.contains = () => true;
    const document = new Element();
    document.querySelector = (selector) => selector === "[data-catalog-url]" ? picker : elements[selector];
    document.createElement = () => new Element();
    const requests = [];
    const navigations = [];
    let scheduled;
    let delay;
    let now = 0;
    const context = {
        document, URL, AbortController,
        window: { location: { origin: "http://localhost", assign: (url) => navigations.push(url) } },
        Option: class extends Element {
            constructor(text, value) { super(); this.textContent = text; this.value = value; }
        },
        Date: { now: () => now },
        setTimeout(callback, milliseconds) { scheduled = callback; delay = milliseconds; return 1; },
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
        requests, navigations, content: elements['[data-catalog-content]'],
        preview: elements['[data-entry-preview]'], previewTitle: elements['[data-entry-title]'],
        previewYear: elements['[data-entry-year]'], previewCover: elements['[data-entry-cover]'],
        selectionPanel: elements['[data-entry-catalog]'], changeGame: elements['[data-entry-change]'],
        flush: () => scheduled(),
        delay: () => delay,
        advanceTime: milliseconds => { now += milliseconds; },
        async search(games) {
            const input = elements[browsing ? "#catalog-query" : "#title"];
            input.value = "Resident";
            input.fire("input");
            const pending = scheduled();
            requests.at(-1).reply({ games });
            await pending;
        },
    };
}

const original = { id: 1, name: "Resident Evil", year: 1996, platforms: ["PC", "PlayStation"] };
const remake = { id: 2, name: "Resident Evil", year: 2002, platforms: ["Nintendo GameCube"] };

test("returning to the input restores recent suggestions without typing or a network request", async () => {
    for (const browsing of [false, true]) {
        const ui = setup(browsing);
        const input = browsing ? ui['catalog-query'] : ui.title;
        await ui.search([original, remake]);
        assert.ok(ui.delay() > 0 && ui.delay() <= 200);
        input.fire('blur');
        assert.equal(ui['catalog-results'].hidden, true);
        input.fire('focus');
        assert.equal(ui['catalog-results'].hidden, false);
        assert.equal(ui['catalog-results'].children.length, 2);
        assert.equal(ui.requests.length, 1);
        input.fire('keydown', { key: 'Escape' });
        input.fire('click');
        assert.equal(ui['catalog-results'].hidden, false);
        assert.equal(ui.requests.length, 1);
    }
});

test("refocusing an interrupted search retries immediately and ignores the old response", async () => {
    const ui = setup();
    ui.title.value = 'Portal';
    ui.title.fire('input');
    const old = ui.flush();
    ui.title.fire('blur');
    const current = ui.title.fire('focus');
    assert.equal(ui.requests.length, 1);
    assert.equal(ui.requests[0].options.signal.aborted, true);
    ui.requests[0].reply({ games: [original] }); await old;
    assert.equal(ui.requests.length, 2);
    assert.equal(ui['catalog-results'].hidden, true);
    ui.requests[1].reply({ games: [remake] }); await current;
    assert.equal(ui['catalog-results'].hidden, false);
    assert.equal(ui['catalog-results'].children[0].children[1].children[0].textContent, remake.name);
});

test("recent suggestions are isolated by content filter and expire before a refocus retry", async () => {
    const ui = setup(true, true);
    const input = ui['catalog-query'];
    await ui.search([original]);
    ui.content.value = 'all'; ui.content.fire('change');
    const all = ui.flush();
    assert.equal(ui.requests.length, 2);
    ui.requests[1].reply({ games: [remake] }); await all;
    ui.content.value = 'official'; ui.content.fire('change');
    assert.equal(ui.requests.length, 2);
    assert.equal(ui['catalog-results'].children[0].children[1].children[0].textContent, original.name);
    input.fire('blur'); ui.advanceTime(120001);
    const fresh = input.fire('focus');
    assert.equal(ui.requests.length, 3);
    ui.requests[2].reply({ games: [] }); await fresh;
    assert.equal(ui['catalog-results'].hidden, true);
});

test("refocusing a selected title does not invalidate its saved platform choice", async () => {
    const ui = setup();
    await ui.search([original]);
    const selection = ui['catalog-results'].children[0].fire('click');
    ui.requests[1].reply({ game: original }); await selection;
    ui.platform.value = 'PC'; ui.platform.fire('change');
    ui.title.fire('blur');
    const suggestions = ui.title.fire('focus');
    assert.equal(ui['igdb-id'].value, '1');
    assert.equal(ui.platform.value, 'PC');
    assert.equal(ui['add-game-button'].disabled, false);
    ui.requests[2].reply({ games: [original] }); await suggestions;
    assert.equal(ui['igdb-id'].value, '1');
    assert.equal(ui.platform.value, 'PC');
});

test("the entry preview follows only the resolved game and clears when searching again", async () => {
    const ui = setup(false, false, true);
    const selected = { ...original, cover_url: 'https://images.igdb.com/igdb/image/upload/t_cover_small/example.jpg' };
    await ui.search([selected]);
    const pending = ui['catalog-results'].children[0].fire('click');
    assert.equal(ui.preview.hidden, true);
    ui.requests.at(-1).reply({ game: selected });
    await pending;
    assert.equal(ui.preview.hidden, false);
    assert.equal(ui.previewTitle.textContent, selected.name);
    assert.equal(ui.previewYear.textContent, selected.year);
    assert.match(ui.previewCover.children[1].src, /\/t_cover_big\//);
    assert.equal(ui.selectionPanel.hidden, true);
    assert.equal(ui.changeGame.attributes['aria-expanded'], 'false');
    ui.changeGame.fire('click');
    assert.equal(ui.selectionPanel.hidden, false);
    assert.equal(ui.changeGame.attributes['aria-expanded'], 'true');
    assert.equal(ui['igdb-id'].value, String(selected.id));
    ui.title.value = 'Portal';
    ui.title.fire('input');
    assert.equal(ui.preview.hidden, true);
    assert.equal(ui['igdb-id'].value, '');
});

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


test("public suggestions open a game by click or keyboard without resolving private form details", async () => {
    for (const keyboard of [false, true]) {
        const ui = setup(true);
        await ui.search([original, remake]);
        assert.match(ui.requests[0].url, /explore\/suggestions\?q=Resident/);
        if (keyboard) {
            ui["catalog-query"].fire("keydown", { key: "ArrowDown" });
            ui["catalog-query"].fire("keydown", { key: "Enter" });
        } else {
            ui["catalog-results"].children[0].fire("click");
        }
        assert.deepEqual(ui.navigations, ["/explore/games/1"]);
        assert.equal(ui.requests.length, 1);
    }
});

test("public suggestions discard stale searches and remain closed after Escape", async () => {
    const ui = setup(true);
    const input = ui["catalog-query"];
    input.value = "god";
    input.fire("input");
    const pending = ui.flush();
    input.value = "gods";
    input.fire("input");
    assert.equal(ui.requests[0].options.signal.aborted, false);
    ui.requests[0].reply({ games: [original] });
    await pending;
    assert.equal(ui["catalog-results"].hidden, true);
    await ui.search([original]);
    input.fire("keydown", { key: "Escape" });
    assert.equal(ui["catalog-results"].hidden, true);
    input.fire("keydown", { key: "Enter" });
    assert.deepEqual(ui.navigations, []);
});

test('changing the content filter cancels stale suggestions and searches the chosen scope', async () => {
    const ui = setup(true, true);
    ui['catalog-query'].value = 'zelda';
    ui['catalog-query'].fire('input');
    const originalRequest = ui.flush();
    assert.match(ui.requests[0].url, /content=official/);
    ui.content.value = 'all';
    ui.content.fire('change');
    const filteredRequest = ui.flush();
    assert.equal(ui.requests.length, 1);
    ui.requests[0].reply({games: [original]}); await originalRequest;
    assert.match(ui.requests[1].url, /content=all/);
    ui.requests[1].reply({games: [remake]}); await filteredRequest;
    assert.equal(ui['catalog-results'].children.length, 1);
    await ui['catalog-results'].children[0].fire('click');
    assert.deepEqual(ui.navigations, ['/explore/games/2']);
});


test('typing during an active search sends only the latest queued query', async () => {
    const ui = setup();
    ui.title.value = 'res'; ui.title.fire('input');
    const first = ui.flush();
    const queued = [];
    for (const term of ['resi', 'resid', 'resident']) {
        ui.title.value = term; ui.title.fire('input');
        queued.push(ui.flush());
    }
    assert.equal(ui.requests.length, 1);
    assert.equal(ui.requests[0].options.signal.aborted, false);
    ui.requests[0].reply({ games: [remake] }); await first;
    assert.equal(ui.requests.length, 2);
    assert.match(ui.requests[1].url, /q=resident$/);
    assert.equal(ui['catalog-results'].hidden, true);
    ui.requests[1].reply({ games: [original] });
    await Promise.all(queued);
    assert.equal(ui['catalog-results'].children.length, 1);
    assert.equal(ui['catalog-results'].children[0].children[1].children[0].textContent, original.name);
});
