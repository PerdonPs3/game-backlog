const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../app/static/welcome.js'), 'utf8');

function setup(reduced = false) {
    const classes = new Set();
    const events = {};
    const timers = new Map();
    const navigations = [];
    const link = { href: 'http://localhost/library', target: '', hasAttribute: () => false,
        addEventListener: (name, fn) => { events[name] = fn; } };
    vm.runInNewContext(source, {
        document: { querySelector: () => link, body: { classList: {
            add: (value) => classes.add(value), remove: (value) => classes.delete(value),
        } } },
        window: { matchMedia: () => ({ matches: reduced }),
            setTimeout: (fn) => { timers.set(1, fn); return 1; },
            clearTimeout: (id) => timers.delete(id),
            location: { assign: (url) => navigations.push(url) },
            addEventListener: (name, fn) => { events[name] = fn; } },
    });
    const click = (extra = {}) => {
        let prevented = false;
        events.click({ button: 0, preventDefault: () => { prevented = true; }, ...extra });
        return prevented;
    };
    return { classes, events, timers, navigations, link, click };
}

test('ordinary click fades before navigating and ignores repeat clicks', () => {
    const state = setup();
    assert.equal(state.click(), true);
    state.click();
    assert.ok(state.classes.has('is-leaving'));
    assert.equal(state.navigations.length, 0);
    assert.equal(state.timers.size, 1);
    state.timers.get(1)();
    assert.deepEqual(state.navigations, ['http://localhost/library']);
});
test('modified clicks and prevented events keep native navigation', () => {
    for (const extra of [{ ctrlKey: true }, { metaKey: true }, { shiftKey: true },
        { altKey: true }, { button: 1 }, { defaultPrevented: true }]) {
        const state = setup();
        assert.equal(state.click(extra), false);
        assert.equal(state.timers.size, 0);
    }
});
test('reduced motion uses native navigation', () => {
    const state = setup(true);
    assert.equal(state.click(), false);
    assert.equal(state.classes.size, 0);
});
test('back navigation resets fade and pending navigation', () => {
    const state = setup();
    state.click();
    state.events.pageshow();
    assert.equal(state.classes.size, 0);
    assert.equal(state.timers.size, 0);
    assert.equal(state.click(), true);
});
test('explicit new tab target is not intercepted', () => {
    const state = setup();
    state.link.target = '_blank';
    assert.equal(state.click(), false);
});
