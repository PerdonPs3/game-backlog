const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const { runInNewContext } = require("node:vm");

class Element {
    constructor() {
        this.listeners = {}; this.children = []; this.style = {}; this.hidden = false;
        this.offsetWidth = 112; this.offsetLeft = 0; this.clientWidth = 600;
        this.classList = { values: new Set(), add(value) { this.values.add(value); } };
    }
    addEventListener(name, callback) { this.listeners[name] = callback; }
    removeEventListener(name) { delete this.listeners[name]; }
    fire(name, extra = {}) {
        const event = { prevented: false, preventDefault() { this.prevented = true; }, ...extra };
        this.listeners[name]?.(event);
        return event;
    }
    append(...nodes) { for (const node of nodes) { node.offsetLeft = this.children.length * 124; this.children.push(node); } }
    focus() { this.focusCount = (this.focusCount || 0) + 1; }
    remove() { this.removed = true; }
}

function setup({ reduced = false, single = false, supported = true, broken = false, games, winnerId = 2, random = 0.5, offscreen = false } = {}) {
    const ids = ["adventure-roulette", "adventure-result", "roulette-track", "roulette-viewport", "roulette-data", "skip-roulette", "roulette-status"];
    const nodes = Object.fromEntries(ids.map((id) => [id, new Element()]));
    const form = new Element(), submit = new Element();
    form.querySelector = () => submit;
    submit.disabled = false;
    const media = new Element(); media.matches = reduced;
    const document = new Element();
    document.querySelector = (selector) => selector === ".adventure-preferences" ? form : nodes[selector.slice(1)];
    document.createElement = () => new Element();
    const window = new Element(); window.matchMedia = () => media;
    let timer;
    window.setTimeout = callback => { timer = callback; return 1; };
    window.clearTimeout = () => { timer = undefined; };
    window.innerHeight = 800;
    if (offscreen) {
        nodes['adventure-roulette'].getBoundingClientRect = () => ({ top: 900, bottom: 1200 });
        nodes['adventure-roulette'].scrollIntoView = options => { nodes['adventure-roulette'].scroll = options; };
    }
    const winner = { id: 2, title: '<script>not HTML</script>', cover_url: null };
    const entries = games || (single ? [winner] : [{ id: 1, title: "Other", cover_url: "https://images.igdb.com/test.jpg" }, winner]);
    nodes["roulette-data"].textContent = JSON.stringify({ winner_id: winnerId, candidate_count: entries.length, games: entries });
    nodes["adventure-roulette"].hidden = true;
    let resolve, reject;
    const animation = { cancelCount: 0, cancel() { this.cancelCount++; }, finished: new Promise((yes, no) => { resolve = yes; reject = no; }) };
    const calls = [];
    if (supported) nodes["roulette-track"].animate = (frames, options) => {
        if (broken) throw new Error("Animation unsupported");
        calls.push({ frames, options }); return animation;
    };
    runInNewContext(readFileSync(join(__dirname, "../app/static/adventure-roulette.js"), "utf8"), {
        document, window, Math: Object.assign(Object.create(Math), { random: () => random }),
    });
    return { ...nodes, form, submit, media, window, document, calls, animation, resolve, reject, timeout: () => timer?.() };
}

test('offscreen reel scrolls into view before starting and starts only once', () => {
    const ui = setup({ offscreen: true });
    assert.equal(ui.calls.length, 0);
    assert.equal(ui['adventure-roulette'].scroll.block, 'center');
    ui.document.fire('scrollend');
    assert.equal(ui.calls.length, 1);
    ui.timeout();
    assert.equal(ui.calls.length, 1);
});

test('scroll fallback starts the reel and skip during scrolling cancels the wait', () => {
    const fallback = setup({ offscreen: true });
    fallback.timeout();
    assert.equal(fallback.calls.length, 1);
    const skipped = setup({ offscreen: true });
    skipped['skip-roulette'].fire('click');
    skipped.timeout();
    skipped.document.fire('scrollend');
    assert.equal(skipped.calls.length, 0);
    assert.equal(skipped['adventure-result'].hidden, false);
    assert.equal(skipped.submit.disabled, false);
});

test("three-second reel lands on server winner and reveals the unchanged result", async () => {
    const ui = setup();
    assert.equal(ui["adventure-result"].hidden, true);
    assert.equal(ui["adventure-roulette"].hidden, false);
    assert.equal(ui.submit.disabled, true);
    assert.equal(ui.calls[0].options.duration, 3000);
    const winner = ui["roulette-track"].children[36];
    assert.equal(winner.children[1].textContent, '<script>not HTML</script>');
    assert.equal(ui.form.fire("submit").prevented, true);
    ui.resolve(); await Promise.resolve();
    assert.equal(ui["adventure-result"].hidden, false);
    assert.equal(winner.classList.values.has("is-winner"), true);
    assert.equal(ui.submit.disabled, false);
    assert.equal(ui["adventure-result"].focusCount, 1);
    assert.equal(ui.form.fire("submit").prevented, false);
});

test("skip reveals immediately and late completion cannot reveal twice", async () => {
    const ui = setup();
    ui["skip-roulette"].fire("click");
    assert.equal(ui["adventure-result"].hidden, false);
    assert.equal(ui["skip-roulette"].hidden, true);
    ui.resolve(); await Promise.resolve();
    assert.equal(ui["adventure-result"].focusCount, 1);
});

test("one matching entry gets a short reveal rather than a fake multi-game spin", async () => {
    const ui = setup({ single: true });
    assert.equal(ui["roulette-track"].children.length, 1);
    assert.equal(ui.calls[0].options.duration, 600);
    ui.resolve(); await Promise.resolve();
    assert.equal(ui["roulette-status"].textContent, "One match. One adventure.");
});

test("reduced motion, missing animation support, and animation failure retain fallback", () => {
    for (const options of [{ reduced: true }, { supported: false }, { broken: true }]) {
        const ui = setup(options);
        assert.equal(ui["adventure-result"].hidden, false);
        assert.equal(ui["adventure-roulette"].hidden, true);
        assert.equal(ui.submit.disabled, false);
    }
});

test("resize and reduced-motion changes finish the spin safely", () => {
    const resized = setup();
    resized.window.fire("resize");
    assert.equal(resized["adventure-result"].hidden, false);
    const preference = setup();
    preference.media.fire("change", { matches: true });
    assert.equal(preference["adventure-result"].hidden, false);
});

test("cover failures remove the image and keep the text placeholder", () => {
    const ui = setup();
    const cover = ui["roulette-track"].children.find((tile) => tile.children[0].children.length === 2).children[0];
    cover.children[1].fire("error");
    assert.equal(cover.children[1].removed, true);
    assert.equal(cover.children[0].textContent, "No cover available");
});

test("all visual neighbours differ, including both sides of every possible winner", () => {
    for (const count of [2, 3, 4, 7, 12]) {
        const games = Array.from({ length: count }, (_, index) => ({ id: index + 1, title: `Game ${index + 1}`, cover_url: null }));
        for (const winnerId of games.map((game) => game.id)) {
            const ui = setup({ games, winnerId });
            const titles = ui["roulette-track"].children.map((tile) => tile.children[1].textContent);
            assert.equal(titles[36], `Game ${winnerId}`);
            for (let index = 1; index < titles.length; index++) {
                assert.notEqual(titles[index], titles[index - 1], `pool ${count}, winner ${winnerId}, slot ${index}`);
            }
        }
    }
});

test("duplicate platform titles are only deduplicated visually, retaining the selected winner", () => {
    const games = [{ id: 1, title: "Same game", cover_url: null },
        { id: 2, title: "Same game", cover_url: "https://images.igdb.com/winner.jpg" },
        { id: 3, title: "Other game", cover_url: null }];
    const ui = setup({ games });
    const tiles = ui["roulette-track"].children;
    assert.equal(tiles[36].children[0].children[1].src, games[1].cover_url);
    for (let index = 1; index < tiles.length; index++) {
        assert.notEqual(tiles[index].children[1].textContent, tiles[index - 1].children[1].textContent);
    }
});

test("one distinct title across several entries uses a short reveal, not repeated covers", () => {
    const ui = setup({ games: [{ id: 1, title: "Same game" }, { id: 2, title: "Same game" }] });
    assert.equal(ui["roulette-track"].children.length, 1);
    assert.equal(ui.calls[0].options.duration, 600);
});

test("visual landing varies inside the winner and skip does not snap it to the centre", () => {
    const positions = [];
    for (const random of [0, 0.25, 0.75, 0.999999]) {
        const ui = setup({ random });
        const tile = ui["roulette-track"].children[36];
        const target = ui.calls[0].frames[1].transform;
        const shift = Number(target.match(/translateX\(([-\d.]+)px\)/)[1]);
        const point = (ui["roulette-viewport"].clientWidth / 2 - tile.offsetLeft - shift) / tile.offsetWidth;
        assert.ok(point >= 0.15 - 1e-10 && point <= 0.85 + 1e-10);
        positions.push(point);
        ui["skip-roulette"].fire("click");
        assert.equal(ui["roulette-track"].style.transform, target);
        assert.equal(tile.classList.values.has("is-winner"), true);
    }
    assert.equal(new Set(positions).size, 4);
});
