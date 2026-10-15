const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const { runInNewContext } = require("node:vm");

function setup(saved = null, blocked = false, present = true) {
    const buttons = ["cards", "shelf"].map((view) => ({
        dataset: { collectionView: view }, attributes: {},
        setAttribute(name, value) { this.attributes[name] = value; },
        addEventListener(name, callback) { this[name] = callback; },
    }));
    const controls = { hidden: true, querySelectorAll: () => buttons };
    const collection = { dataset: {}, innerHTML: "Original cards" };
    const writes = [];
    runInNewContext(readFileSync(join(__dirname, "../app/static/collection-view.js"), "utf8"), {
        document: { querySelector: (selector) => !present ? null : selector === "#collection-view-switch" ? controls : collection },
        window: { localStorage: {
            getItem() { if (blocked) throw new Error("Blocked"); return saved; },
            setItem(key, value) { if (blocked) throw new Error("Blocked"); writes.push([key, value]); },
        } },
    });
    return { controls, collection, buttons, writes };
}

test("defaults to cards and switches layout without replacing collection content", () => {
    const ui = setup();
    assert.equal(ui.controls.hidden, false);
    assert.equal(ui.collection.dataset.view, "cards");
    ui.buttons[1].click();
    assert.equal(ui.collection.dataset.view, "shelf");
    assert.equal(ui.buttons[0].attributes["aria-pressed"], "false");
    assert.equal(ui.buttons[1].attributes["aria-pressed"], "true");
    assert.equal(ui.collection.innerHTML, "Original cards");
    assert.deepEqual(ui.writes, [["game-backlog.collection-view", "shelf"]]);
});

test("restores saved shelf and keeps it when filtering replaces the cards", () => {
    const ui = setup("shelf");
    ui.collection.innerHTML = "Filtered cards";
    assert.equal(ui.collection.dataset.view, "shelf");
    ui.buttons[0].click();
    assert.equal(ui.collection.dataset.view, "cards");
    assert.equal(ui.buttons[0].attributes["aria-pressed"], "true");
});

test("blocked storage does not break switching and invalid preferences default to cards", () => {
    const ui = setup(null, true);
    ui.buttons[1].click();
    assert.equal(ui.collection.dataset.view, "shelf");
    assert.equal(setup("not-a-view").collection.dataset.view, "cards");
});

test("pages without collection controls remain unaffected", () => {
    assert.doesNotThrow(() => setup(null, false, false));
});
