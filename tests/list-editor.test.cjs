const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const { runInNewContext } = require("node:vm");

function setup(view = "all", selected = [true, false, true]) {
    const buttons = ["all", "selected"].map((value) => ({ dataset: { listView: value }, attributes: {},
        setAttribute(key, value) { this.attributes[key] = value; }, addEventListener(name, fn) { this[name] = fn; } }));
    const rows = selected.map((checked) => {
        const input = { checked, addEventListener(name, fn) { this[name] = fn; } };
        return { input, querySelector: () => input };
    });
    const toolbar = { querySelectorAll: () => buttons, hidden: true };
    const viewInput = { value: view }, count = {}, empty = {};
    const nodes = { "#list-editor-toolbar": toolbar, "#list-editor-view": viewInput,
        "#list-selected-count": count, "#list-selection-empty": empty };
    runInNewContext(readFileSync(join(__dirname, "../app/static/list-editor.js"), "utf8"), {
        document: { querySelector: (selector) => nodes[selector],
            querySelectorAll: (selector) => selector === ".list-game-choice" ? rows : [] },
    });
    return { rows, buttons, viewInput, count, empty, toolbar };
}

test("selected-only view hides unchecked rows without changing or disabling inputs", () => {
    const ui = setup();
    ui.buttons[1].click();
    assert.deepEqual(ui.rows.map((row) => row.hidden), [false, true, false]);
    assert.deepEqual(ui.rows.map((row) => row.input.checked), [true, false, true]);
    assert.ok(ui.rows.every((row) => row.input.disabled === undefined));
    assert.equal(ui.viewInput.value, "selected");
    assert.equal(ui.count.textContent, "2 entries selected");
    assert.equal(ui.buttons[1].attributes["aria-pressed"], "true");
    ui.buttons[0].click();
    assert.ok(ui.rows.every((row) => !row.hidden));
});

test("unchecking the last selected game updates count and provides empty-state help", () => {
    const ui = setup("selected", [true, false]);
    ui.rows[0].input.checked = false;
    ui.rows[0].input.change();
    assert.equal(ui.count.textContent, "0 entries selected");
    assert.equal(ui.empty.hidden, false);
    assert.ok(ui.rows.every((row) => row.hidden));
    ui.buttons[0].click();
    assert.equal(ui.empty.hidden, true);
});

test("restores view on returning from Save list and ignores an invalid view", () => {
    assert.equal(setup("selected").rows[1].hidden, true);
    assert.ok(setup("invalid").rows.every((row) => !row.hidden));
});
