const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { runInNewContext } = require('node:vm');

function setup(reduced = false) {
    const root = { dataset: {} }, events = {};
    runInNewContext(readFileSync('app/static/room-navigation.js', 'utf8'), {
        document: { documentElement: root },
        window: {
            matchMedia: () => ({ matches: reduced }),
            addEventListener: (name, callback) => { events[name] = callback; },
        },
    });
    return { root, events };
}

test('navigation animation is limited to an active document transition', () => {
    const ui = setup();
    ui.events.pagereveal({ viewTransition: null });
    assert.equal(ui.root.dataset.roomNavigation, undefined);
    assert.equal(ui.events.click, undefined);
    assert.equal(ui.events.submit, undefined);
});

test('both navigation directions remove their styles after finishing or cancellation', async () => {
    for (const name of ['pageswap', 'pagereveal']) {
        for (const cancel of [false, true]) {
            const ui = setup();
            let finish, reject;
            const finished = new Promise((resolve, fail) => { finish = resolve; reject = fail; });
            ui.events[name]({ viewTransition: { finished } });
            assert.equal(ui.root.dataset.roomNavigation, 'true');
            if (cancel) reject(new Error('Navigation cancelled'));
            else finish();
            await Promise.resolve();
            assert.equal(ui.root.dataset.roomNavigation, undefined);
        }
    }
});

test('reduced motion skips the transition without changing page styles', () => {
    const ui = setup(true);
    let skips = 0;
    ui.events.pagereveal({ viewTransition: { skipTransition() { skips++; } } });
    assert.equal(skips, 1);
    assert.equal(ui.root.dataset.roomNavigation, undefined);
});
