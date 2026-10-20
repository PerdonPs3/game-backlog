const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { runInNewContext } = require('node:vm');
const { join } = require('node:path');

function setup({ reduced = false, observer = true } = {}) {
    const events = {}, timers = new Map();
    let next = 0, intersect;
    const control = { hidden: true, addEventListener(_, fn) { this.click = fn; }, setAttribute(_, value) { this.label = value; } };
    const frames = [0, 1, 2].map(step => ({ dataset: { demoFrame: String(step) } }));
    const demo = { dataset: { productDemo: 'library' }, querySelector: () => control, querySelectorAll: () => frames };
    const motion = { matches: reduced, addEventListener(_, fn) { this.change = fn; } };
    const document = { hidden: false, querySelectorAll: () => [demo], addEventListener: (event, fn) => { events[event] = fn; } };
    const window = {
        matchMedia: () => motion,
        setTimeout(fn) { timers.set(++next, fn); return next; }, clearTimeout(id) { timers.delete(id); },
        addEventListener: (event, fn) => { events[event] = fn; },
    };
    if (observer) window.IntersectionObserver = class { constructor(fn) { intersect = fn; } observe() {} };
    runInNewContext(readFileSync(join(__dirname, '../app/static/product-demos.js'), 'utf8'), { window, document });
    return { demo, control, frames, motion, document, events, timers,
        visible(value) { intersect([{ isIntersecting: value }]); },
        tick() { const [id, fn] = timers.entries().next().value; timers.delete(id); fn(); },
    };
}

test('plays once on entry, presents a static ending, and replays on request', () => {
    const ui = setup();
    assert.equal(ui.demo.dataset.step, '2'); assert.equal(ui.timers.size, 0);
    ui.visible(true); assert.equal(ui.demo.dataset.step, '0');
    assert.deepEqual(ui.frames.map(frame => frame.hidden), [false, true, true]);
    ui.tick(); assert.equal(ui.demo.dataset.step, '1');
    ui.tick(); assert.equal(ui.demo.dataset.step, '2'); assert.equal(ui.timers.size, 0);
    ui.visible(false); ui.visible(true); assert.equal(ui.demo.dataset.step, '2');
    ui.control.click(); assert.equal(ui.demo.dataset.step, '0'); assert.equal(ui.timers.size, 1);
});

test('pauses offscreen, in hidden tabs, and when the viewer presses Pause', () => {
    const ui = setup(); ui.visible(true); ui.tick();
    ui.visible(false); assert.equal(ui.timers.size, 0);
    ui.visible(true); assert.equal(ui.timers.size, 1);
    ui.document.hidden = true; ui.events.visibilitychange(); assert.equal(ui.timers.size, 0);
    ui.document.hidden = false; ui.events.visibilitychange(); assert.equal(ui.timers.size, 1);
    ui.control.click(); assert.equal(ui.timers.size, 0); assert.equal(ui.control.label, 'Play library demo');
    ui.visible(false); ui.visible(true); assert.equal(ui.timers.size, 0);
    ui.control.click(); assert.equal(ui.timers.size, 1);
    ui.events.pagehide(); assert.equal(ui.timers.size, 0);
    ui.events.pageshow(); assert.equal(ui.timers.size, 1);
});

test('reduced motion always shows the final state, including a live preference change', () => {
    const reduced = setup({ reduced: true }); reduced.visible(true);
    assert.equal(reduced.demo.dataset.step, '2'); assert.equal(reduced.control.hidden, true);
    assert.equal(reduced.timers.size, 0);
    const ui = setup(); ui.visible(true); ui.motion.matches = true; ui.motion.change();
    assert.equal(ui.demo.dataset.step, '2'); assert.equal(ui.timers.size, 0);
    assert.deepEqual(ui.frames.map(frame => frame.hidden), [true, true, false]);
});

test('without intersection observation, the static example can still be replayed manually', () => {
    const ui = setup({ observer: false }); assert.equal(ui.timers.size, 0);
    ui.control.click(); ui.tick(); assert.equal(ui.demo.dataset.step, '1');
});
