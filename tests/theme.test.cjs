const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const { runInNewContext } = require("node:vm");

function setup({ saved = null, light = false, blocked = false, animated = false, reduced = false } = {}) {
    const root = { dataset: {} }, events = {}, mediaEvents = {}, writes = [], transitions = [];
    const caption = {};
    const button = { hidden: true, attributes: {},
        setAttribute(name, value) { this.attributes[name] = value; },
        querySelector: () => caption, addEventListener(name, callback) { this[name] = callback; } };
    let ready = false;
    const document = { documentElement: root,
        querySelectorAll: () => ready ? [button] : [],
        addEventListener(name, callback) { events[name] = callback; } };
    if (animated) document.startViewTransition = (callback) => {
        const transition = { finished: Promise.resolve(), skips: 0, skipTransition() { this.skips++; } };
        transitions.push(transition);
        callback();
        return transition;
    };
    const media = { matches: light, addEventListener(name, callback) { mediaEvents[name] = callback; } };
    const window = { matchMedia: (query) => query.includes("reduced-motion") ? { matches: reduced } : media,
        localStorage: { getItem() { if (blocked) throw new Error("Blocked"); return saved; },
            setItem(key, value) { if (blocked) throw new Error("Blocked"); writes.push([key, value]); } },
        addEventListener(name, callback) { events[name] = callback; } };
    runInNewContext(readFileSync(join(__dirname, "../app/static/theme.js"), "utf8"), { document, window });
    return { root, button, caption, writes, media, events, transitions,
        ready() { ready = true; events.DOMContentLoaded(); },
        system(light) { media.matches = light; mediaEvents.change(); },
    };
}

test("applies system theme before page content loads and reveals the accessible toggle", () => {
    const ui = setup({ light: true });
    assert.equal(ui.root.dataset.theme, "light");
    assert.equal(ui.button.hidden, true);
    ui.ready();
    assert.equal(ui.button.hidden, false);
    assert.equal(ui.button.attributes["aria-label"], "Switch to dark mode");
});

test("saved preference overrides system and switching remembers the next theme", () => {
    const ui = setup({ saved: "dark", light: true }); ui.ready();
    assert.equal(ui.root.dataset.theme, "dark");
    ui.button.click();
    assert.equal(ui.root.dataset.theme, "light");
    assert.deepEqual(ui.writes, [["game-backlog.theme", "light"]]);
    assert.equal(ui.button.attributes.title, "Switch to dark mode");
    ui.system(false);
    assert.equal(ui.root.dataset.theme, "light");
});

test("follows system changes until an explicit selection is made", () => {
    const ui = setup(); ui.ready();
    ui.system(true);
    assert.equal(ui.root.dataset.theme, "light");
    ui.button.click();
    ui.system(true);
    assert.equal(ui.root.dataset.theme, "dark");
});

test("invalid preferences and blocked storage never prevent switching", () => {
    const invalid = setup({ saved: "not-a-theme", light: true });
    assert.equal(invalid.root.dataset.theme, "light");
    const ui = setup({ blocked: true }); ui.ready();
    ui.button.click();
    assert.equal(ui.root.dataset.theme, "light");
    ui.button.click();
    assert.equal(ui.root.dataset.theme, "dark");
});

test("synchronizes other tabs and returns to system when the preference is cleared", () => {
    const ui = setup({ saved: "dark", light: true }); ui.ready();
    ui.events.storage({ key: "game-backlog.theme", newValue: "light" });
    assert.equal(ui.root.dataset.theme, "light");
    ui.events.storage({ key: "unrelated", newValue: "dark" });
    assert.equal(ui.root.dataset.theme, "light");
    ui.events.storage({ key: "game-backlog.theme", newValue: null });
    ui.system(false);
    assert.equal(ui.root.dataset.theme, "dark");
});

test("animates explicit switches but not page initialization", () => {
    const ui = setup({ animated: true }); ui.ready();
    assert.equal(ui.transitions.length, 0);
    ui.button.click();
    assert.equal(ui.transitions.length, 1);
    assert.equal(ui.root.dataset.theme, "light");
    ui.button.click();
    assert.equal(ui.transitions[0].skips, 1);
    assert.equal(ui.root.dataset.theme, "dark");
});

test("reduced-motion preference bypasses palette animations", () => {
    const ui = setup({ animated: true, reduced: true }); ui.ready();
    ui.button.click();
    assert.equal(ui.transitions.length, 0);
    assert.equal(ui.root.dataset.theme, "light");
});

test("light theme readable foregrounds contrast with their intended surfaces", () => {
    const luminance = (hex) => {
        const channels = hex.match(/[a-f\d]{2}/gi).map((part) => parseInt(part, 16) / 255)
            .map((value) => value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4);
        return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722;
    };
    for (const [foreground, background] of [["29213d", "ffffff"], ["665d75", "faf8f5"],
        ["7042b7", "ffffff"], ["ffffff", "8250bf"], ["613297", "f2ecfa"]]) {
        const levels = [luminance(foreground), luminance(background)].sort((a, b) => a - b);
        assert.ok((levels[1] + 0.05) / (levels[0] + 0.05) >= 4.5, `${foreground}/${background}`);
    }
});
