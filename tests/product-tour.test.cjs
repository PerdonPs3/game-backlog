const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { runInNewContext } = require('node:vm');
const { join } = require('node:path');

function setup({ reduced = false, observer = true } = {}) {
    const observed = new Set(), events = {};
    let reveal, disconnected = 0;
    const chapters = [0, 1, 2, 3].map(() => {
        const classes = new Set();
        return { classList: { add: name => classes.add(name), contains: name => classes.has(name) } };
    });
    const motion = { matches: reduced, addEventListener(_, callback) { this.change = callback; } };
    const window = { matchMedia: () => motion, addEventListener: (name, callback) => { events[name] = callback; } };
    if (observer) window.IntersectionObserver = class {
        constructor(callback) { reveal = callback; }
        observe(chapter) { observed.add(chapter); }
        unobserve(chapter) { observed.delete(chapter); }
        disconnect() { observed.clear(); disconnected++; }
    };
    runInNewContext(readFileSync(join(__dirname, '../app/static/product-tour.js'), 'utf8'), {
        window, document: { querySelectorAll: () => chapters },
    });
    return { chapters, observed, motion, events, reveal: entries => reveal(entries), disconnected: () => disconnected };
}

test('chapters reveal independently on entry and stop observation after their first reveal', () => {
    const ui = setup();
    assert.equal(ui.observed.size, 4);
    ui.reveal([{ target: ui.chapters[0], isIntersecting: false }]);
    assert.equal(ui.chapters[0].classList.contains('is-revealed'), false);
    ui.reveal([{ target: ui.chapters[0], isIntersecting: true }]);
    assert.equal(ui.chapters[0].classList.contains('is-revealed'), true);
    assert.equal(ui.observed.size, 3);
    assert.equal(ui.chapters[1].classList.contains('is-revealed'), false);
    ui.events.pagehide(); assert.equal(ui.observed.size, 0);
    ui.events.pageshow(); assert.equal(ui.observed.size, 3);
});

test('reduced motion reveals all chapters and handles a live preference change', () => {
    const ui = setup({ reduced: true });
    assert.equal(ui.observed.size, 0);
    assert.ok(ui.chapters.every(chapter => chapter.classList.contains('is-revealed')));
    const live = setup(); live.motion.matches = true; live.motion.change();
    assert.equal(live.observed.size, 0);
    assert.ok(live.chapters.every(chapter => chapter.classList.contains('is-revealed')));
    live.motion.matches = false; live.motion.change();
    assert.equal(live.observed.size, 0);
});

test('browsers without intersection observation keep the static document intact', () => {
    const ui = setup({ observer: false });
    assert.equal(ui.observed.size, 0);
    assert.equal(ui.disconnected(), 0);
});
