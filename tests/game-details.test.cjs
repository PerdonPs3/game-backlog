const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const { runInNewContext } = require("node:vm");

class Element {
    constructor() { this.listeners = {}; this.attributes = {}; this.children = []; }
    addEventListener(name, fn) { this.listeners[name] = fn; }
    fire(name, extra = {}) {
        const event = { prevented: false, preventDefault() { this.prevented = true; }, ...extra };
        const done = this.listeners[name]?.(event);
        return { event, done };
    }
    focus() { this.focused = true; }
    setAttribute(name, value) { this.attributes[name] = value; }
    showModal() { this.open = true; }
    close() { this.open = false; this.fire("close"); }
    append(node) { this.children.push(node); }
    querySelector() { return null; }
}

function setup(supported = true) {
    const dialog = new Element(), content = new Element(), close = new Element();
    const nodes = { "game-details-dialog": dialog, "game-details-content": content, "close-game-details": close };
    const document = new Element();
    document.querySelector = (selector) => nodes[selector.slice(1)];
    document.createElement = () => new Element();
    if (!supported) dialog.showModal = undefined;
    const requests = [];
    const fetch = (url, options) => new Promise((resolve, reject) => requests.push({ url, options, resolve, reject }));
    runInNewContext(readFileSync(join(__dirname, "../app/static/game-details.js"), "utf8"), {
        document, fetch, AbortController,
    });
    return { dialog, content, close, requests,
        click(id = 1, extra = {}) {
            const link = new Element();
            link.href = `http://localhost/games/${id}`;
            link.isConnected = true;
            link.closest = () => link;
            return { link, ...document.fire("click", { target: link, button: 0, ...extra }) };
        },
    };
}

test("opens from a delegated card link, loads fragment, and restores focus", async () => {
    const ui = setup();
    const click = ui.click(4);
    assert.equal(click.event.prevented, true);
    assert.equal(ui.dialog.open, true);
    assert.equal(ui.close.focused, true);
    assert.equal(ui.content.attributes["aria-busy"], "true");
    assert.equal(ui.requests[0].options.headers.Accept, "application/json");
    ui.requests[0].resolve({ ok: true, json: async () => ({ html: "<h2>Portal</h2>" }) });
    await click.done;
    assert.equal(ui.content.innerHTML, "<h2>Portal</h2>");
    assert.equal(ui.content.attributes["aria-busy"], "false");
    ui.close.fire("click");
    assert.equal(ui.dialog.open, false);
    assert.equal(click.link.focused, true);
});

test("closing aborts loading and ignores an old response after reopening", async () => {
    const ui = setup();
    const old = ui.click(1);
    ui.dialog.close();
    assert.equal(ui.requests[0].options.signal.aborted, true);
    const next = ui.click(2);
    ui.requests[1].resolve({ ok: true, json: async () => ({ html: "New game" }) });
    await next.done;
    ui.requests[0].resolve({ ok: true, json: async () => ({ html: "Old game" }) });
    await old.done;
    assert.equal(ui.content.innerHTML, "New game");
});

test("request errors offer a normal page fallback without exposing errors", async () => {
    const ui = setup();
    const click = ui.click();
    ui.requests[0].reject(new Error("private upstream detail"));
    await click.done;
    assert.match(ui.content.textContent, /Could not load/);
    assert.equal(ui.content.children[0].href, click.link.href);
    assert.equal(ui.content.attributes["aria-busy"], "false");
});

test("unsupported dialogs and modified clicks retain navigation", () => {
    assert.equal(setup(false).click().event.prevented, false);
    for (const key of ["ctrlKey", "metaKey", "shiftKey", "altKey"]) {
        const ui = setup();
        assert.equal(ui.click(1, { [key]: true }).event.prevented, false);
        assert.equal(ui.requests.length, 0);
    }
});
