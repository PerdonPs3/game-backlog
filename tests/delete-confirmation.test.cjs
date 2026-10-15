const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const { runInNewContext } = require("node:vm");

class Element {
    constructor() { this.listeners = {}; this.attributes = {}; this.open = false; }
    addEventListener(name, fn) { this.listeners[name] = fn; }
    fire(name, extra = {}) {
        const event = { prevented: false, preventDefault() { this.prevented = true; }, ...extra };
        this.listeners[name]?.(event);
        return event;
    }
    focus() { this.focused = true; }
    set action(value) { this.attributes.action = value; }
    get action() { return this.attributes.action; }
    hasAttribute(name) { return name in this.attributes; }
    removeAttribute(name) { delete this.attributes[name]; }
    showModal() { this.open = true; }
    close() { this.open = false; this.fire("close"); }
}

function setup(supported = true) {
    const ids = ["delete-game-dialog", "delete-game-form", "delete-game-title", "cancel-delete", "confirm-delete"];
    const nodes = Object.fromEntries(ids.map((id) => [id, new Element()]));
    const document = new Element();
    document.querySelector = (selector) => nodes[selector.slice(1)];
    nodes["delete-game-dialog"].querySelector = document.querySelector;
    if (!supported) nodes["delete-game-dialog"].showModal = undefined;
    runInNewContext(readFileSync(join(__dirname, "../app/static/delete-confirmation.js"), "utf8"), { document });
    return { ...nodes, document,
        click(id = 1, title = "Portal 2", extra = {}) {
            const link = new Element();
            link.href = `http://localhost/games/${id}/delete`;
            link.dataset = { gameTitle: title };
            link.isConnected = true;
            link.closest = (selector) => selector === "#game-collection" ? {} : link;
            return { link, event: document.fire("click", { target: link, button: 0, ...extra }) };
        },
    };
}

test("opens confirmation without navigation, safely displays the selected title", () => {
    const ui = setup();
    const title = '<img src=x onerror="alert(1)">';
    const { event } = ui.click(3, title);
    assert.equal(event.prevented, true);
    assert.equal(ui["delete-game-dialog"].open, true);
    assert.equal(ui["delete-game-form"].action, "http://localhost/games/3/delete");
    assert.equal(ui["delete-game-title"].textContent, title);
    assert.equal(ui["cancel-delete"].focused, true);
});

test("cancel closes without submitting, resets state, and restores focus", () => {
    const ui = setup();
    const { link } = ui.click();
    ui["cancel-delete"].fire("click");
    assert.equal(ui["delete-game-dialog"].open, false);
    assert.equal(ui["delete-game-form"].hasAttribute("action"), false);
    assert.equal(ui["confirm-delete"].disabled, true);
    assert.equal(link.focused, true);
});

test("Escape is allowed before confirmation and subsequent filtered cards work", () => {
    const ui = setup();
    ui.click(1);
    assert.equal(ui["delete-game-dialog"].fire("cancel").prevented, false);
    ui["delete-game-dialog"].close();
    ui.click(4, "Resident Evil");
    assert.equal(ui["delete-game-form"].action, "http://localhost/games/4/delete");
    assert.equal(ui["delete-game-title"].textContent, "Resident Evil");
});

test("confirmation permits one native POST, then blocks duplicate submission", () => {
    const ui = setup();
    assert.equal(ui["delete-game-form"].fire("submit").prevented, true);
    ui.click();
    assert.equal(ui["delete-game-form"].fire("submit").prevented, false);
    assert.equal(ui["confirm-delete"].disabled, true);
    assert.equal(ui["delete-game-form"].fire("submit").prevented, true);
    assert.equal(ui["delete-game-dialog"].fire("cancel").prevented, true);
});

test("unsupported dialogs and modified clicks preserve the normal link fallback", () => {
    assert.equal(setup(false).click().event.prevented, false);
    assert.equal(setup().click(1, "Game", { ctrlKey: true }).event.prevented, false);
});
