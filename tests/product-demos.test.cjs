const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { runInNewContext } = require('node:vm');
const { join } = require('node:path');

function setup({ reduced = false, observer = true, kind = 'library' } = {}) {
    const events = {}, timers = new Map();
    let next = 0, intersect;
    const control = { hidden: true, attributes: {}, addEventListener(_, fn) { this.click = fn; }, setAttribute(key, value) { this.attributes[key] = value; } };
    const frames = [0, 1, 2].map(step => ({ dataset: { demoFrame: String(step) } }));
    const field = { dataset: { demoType: kind === 'search' ? 'search' : 'review', demoText: kind === 'search' ? 'Hollow Knight' : 'A world I did not want to leave.' }, textContent: '' };
    const stars = { dataset: {} }, saved = { dataset: {} };
    const demo = { dataset: { productDemo: kind },
        querySelector: selector => selector === '[data-demo-control]' ? control : saved,
        querySelectorAll: selector => selector === '[data-demo-frame]' ? frames : selector === '[data-demo-type]' ? [field] : [stars] };
    const motion = { matches: reduced, addEventListener(_, fn) { this.change = fn; } };
    const document = { hidden: false, querySelectorAll: () => [demo], addEventListener: (event, fn) => { events[event] = fn; } };
    const window = {
        matchMedia: () => motion,
        setTimeout(fn) { timers.set(++next, fn); return next; }, clearTimeout(id) { timers.delete(id); },
        addEventListener: (event, fn) => { events[event] = fn; },
    };
    if (observer) window.IntersectionObserver = class { constructor(fn) { intersect = fn; } observe() {} };
    runInNewContext(readFileSync(join(__dirname, '../app/static/product-demos.js'), 'utf8'), { window, document });
    return { demo, control, field, stars, saved, frames, motion, document, events, timers,
        visible(value) { intersect([{ isIntersecting: value }]); },
        tick(count = 1) { for (let i = 0; i < count; i++) { const [id, fn] = timers.entries().next().value; timers.delete(id); fn(); } },
    };
}

test('visible search types a query and loops from the saved state without Replay', () => {
    const ui = setup({ kind: 'search' });
    assert.equal(ui.timers.size, 0);
    ui.visible(true); assert.equal(ui.field.textContent, '');
    ui.tick(8); assert.equal(ui.field.textContent, 'Hollow');
    ui.tick(25); assert.equal(ui.demo.dataset.step, '1');
    assert.equal(ui.field.textContent, 'Hollow Knight');
    ui.tick(35); assert.equal(ui.demo.dataset.step, '2');
    ui.tick(43); assert.equal(ui.demo.dataset.step, '0');
    assert.equal(ui.field.textContent, '');
    assert.equal(ui.timers.size, 1);
    assert.equal(ui.control.textContent, 'Pause Ⅱ');
});

test('library adds a game, selects stars, writes a review, saves and starts again', () => {
    const ui = setup(); ui.visible(true);
    ui.tick(28); assert.equal(ui.demo.dataset.step, '1');
    ui.tick(33); assert.equal(ui.demo.dataset.step, '2');
    ui.tick(8); assert.equal(ui.stars.dataset.rating, '3');
    assert.equal(ui.field.textContent, '');
    ui.tick(15); assert.equal(ui.stars.dataset.rating, '5');
    assert.ok(ui.field.textContent.length > 0);
    assert.ok(ui.field.textContent.length < ui.field.dataset.demoText.length);
    ui.tick(45); assert.equal(ui.field.textContent, ui.field.dataset.demoText);
    assert.equal(ui.saved.dataset.saved, 'true');
    ui.tick(14); assert.equal(ui.demo.dataset.step, '0');
    assert.equal(ui.saved.dataset.saved, 'false');
    assert.equal(ui.field.textContent, '');
});

test('pause freezes typing and timers across offscreen and page lifecycle changes', () => {
    const ui = setup({ kind: 'search' }); ui.visible(true); ui.tick(5);
    const text = ui.field.textContent;
    ui.control.click(); assert.equal(ui.timers.size, 0);
    assert.equal(ui.control.attributes['aria-pressed'], 'true');
    assert.equal(ui.field.dataset.writing, 'false');
    ui.visible(false); ui.visible(true); assert.equal(ui.timers.size, 0);
    ui.control.click(); assert.equal(ui.field.textContent, text);
    assert.equal(ui.timers.size, 1);
    ui.document.hidden = true; ui.events.visibilitychange(); assert.equal(ui.timers.size, 0);
    ui.document.hidden = false; ui.events.visibilitychange(); assert.equal(ui.timers.size, 1);
    ui.visible(false); assert.equal(ui.timers.size, 0);
    ui.visible(true); assert.equal(ui.timers.size, 1);
    ui.events.pagehide(); ui.events.visibilitychange(); assert.equal(ui.timers.size, 0);
    ui.events.pageshow(); assert.equal(ui.timers.size, 1);
});

test('reduced motion displays the complete static result with no typing or timers', () => {
    const ui = setup({ reduced: true }); ui.visible(true);
    assert.equal(ui.demo.dataset.step, '2'); assert.equal(ui.control.hidden, true);
    assert.equal(ui.timers.size, 0);
    assert.equal(ui.field.textContent, ui.field.dataset.demoText);
    assert.equal(ui.stars.dataset.rating, '5');
    const live = setup(); live.visible(true); live.tick();
    live.motion.matches = true; live.motion.change();
    assert.equal(live.timers.size, 0); assert.equal(live.demo.dataset.step, '2');
    assert.equal(live.field.textContent, live.field.dataset.demoText);
});

test('without intersection observation the loop still has working pause controls', () => {
    const ui = setup({ observer: false }); assert.equal(ui.timers.size, 1);
    ui.tick(); ui.control.click(); assert.equal(ui.timers.size, 0);
    ui.control.click(); assert.equal(ui.timers.size, 1);
});
