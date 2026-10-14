const { test } = require("node:test");
const assert = require("node:assert/strict");
const { runInNewContext } = require("node:vm");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");

function setup({ fine = true, reduced = false, withLogo = true } = {}) {
    const documentEvents = {};
    const windowEvents = {};
    const frames = new Map();
    const classes = new Set();
    const glow = {
        style: {}, attributes: {},
        setAttribute(name, value) { this.attributes[name] = value; },
        classList: { add: (name) => classes.add(name), remove: (name) => classes.delete(name) },
    };
    const logo = {
        style: { setProperty(name, value) { this[name] = value; } },
        getBoundingClientRect: () => ({ left: 20, right: 62, top: 12, bottom: 60 }),
    };
    const mouse = { matches: fine, addEventListener(name, fn) { this.change = fn; } };
    const motion = { matches: reduced, addEventListener(name, fn) { this.change = fn; } };
    const document = {
        body: { append(node) { assert.equal(node, glow); } },
        createElement: () => glow,
        querySelector: () => withLogo ? logo : null,
        addEventListener(name, fn) { documentEvents[name] = fn; },
    };
    let sequence = 0;
    runInNewContext(readFileSync(join(__dirname, "../app/static/cursor-glow.js"), "utf8"), {
        document,
        window: {
            matchMedia: (query) => query.includes("prefers-reduced-motion") ? motion : mouse,
            addEventListener(name, fn) { windowEvents[name] = fn; },
            requestAnimationFrame(fn) { const id = ++sequence; frames.set(id, fn); return id; },
            cancelAnimationFrame(id) { frames.delete(id); },
        },
    });
    return { document, documentEvents, windowEvents, frames, glow, logo, classes, motion,
        move(extra = {}) { documentEvents.pointermove({ pointerType: "mouse", clientX: 400, clientY: 300, ...extra }); },
        paint() { const callbacks = [...frames.values()]; frames.clear(); callbacks.forEach((fn) => fn()); },
    };
}

test("glow is decorative and batches moves into one frame at the latest position", () => {
    const ui = setup();
    assert.equal(ui.glow.attributes["aria-hidden"], "true");
    ui.move();
    ui.move({ clientX: 500, clientY: 350 });
    assert.equal(ui.frames.size, 1);
    ui.paint();
    assert.equal(ui.glow.style.transform, "translate3d(220px, 70px, 0)");
    assert.equal(ui.classes.has("is-visible"), true);
});

test("touch, coarse pointers, and reduced motion do not animate", () => {
    for (const options of [{ fine: false }, { reduced: true }, {}]) {
        const ui = setup(options);
        ui.move(options.fine === undefined && options.reduced === undefined ? { pointerType: "touch" } : {});
        assert.equal(ui.frames.size, 0);
        assert.equal(ui.classes.has("is-visible"), false);
    }
});

test("leaving the page cancels pending frames and hides the glow", () => {
    const ui = setup();
    ui.move();
    ui.documentEvents.pointerleave();
    assert.equal(ui.frames.size, 0);
    ui.move();
    ui.paint();
    ui.windowEvents.blur();
    assert.equal(ui.classes.has("is-visible"), false);
});

test("changing accessibility settings immediately hides the glow", () => {
    const ui = setup();
    ui.move();
    ui.paint();
    ui.motion.matches = true;
    ui.motion.change();
    ui.move();
    assert.equal(ui.classes.has("is-visible"), false);
    assert.equal(ui.frames.size, 0);
});

test("logo gradually lights up near the cursor and dims outside the light", () => {
    const ui = setup();
    ui.move({ clientX: 600, clientY: 400 });
    ui.paint();
    assert.equal(Number(ui.logo.style["--logo-light"]), 0);
    ui.move({ clientX: 160, clientY: 30 });
    ui.paint();
    const partial = Number(ui.logo.style["--logo-light"]);
    assert.ok(partial > 0 && partial < 1);
    ui.move({ clientX: 40, clientY: 30 });
    ui.paint();
    assert.equal(Number(ui.logo.style["--logo-light"]), 1);
    ui.documentEvents.pointerleave();
    assert.equal(Number(ui.logo.style["--logo-light"]), 0);
});

test("logo light resets when reduced motion is enabled", () => {
    const ui = setup();
    ui.move({ clientX: 40, clientY: 30 });
    ui.paint();
    assert.equal(Number(ui.logo.style["--logo-light"]), 1);
    ui.motion.matches = true;
    ui.motion.change();
    assert.equal(Number(ui.logo.style["--logo-light"]), 0);
});

test("glow still works on pages without a logo", () => {
    const ui = setup({ withLogo: false });
    ui.move();
    ui.paint();
    assert.equal(ui.classes.has("is-visible"), true);
});
