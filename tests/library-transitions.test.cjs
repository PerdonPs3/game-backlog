const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const { runInNewContext } = require('node:vm');
const source = readFileSync(join(__dirname, '../app/static/library-transitions.js'), 'utf8');

function setup({ reduced = false, activation } = {}) {
    const events = {};
    const dataset = {};
    const motion = { matches: reduced, addEventListener: (name, fn) => events.motion = fn };
    runInNewContext(source, {
        URL,
        document: { documentElement: { dataset } },
        window: {
            location: { href: 'http://localhost/library', origin: 'http://localhost' },
            navigation: { activation },
            matchMedia: () => motion,
            addEventListener: (name, fn) => events[name] = fn,
        },
    });
    return { events, dataset };
}
function route(from, to) {
    return { from: { url: from }, entry: { url: to } };
}
function transition() {
    let finish;
    return { skipped: false, finished: new Promise(resolve => finish = resolve),
        finish: () => finish(), skipTransition() { this.skipped = true; } };
}

test('outgoing and incoming documents agree on room direction without saved browsing state', async () => {
    for (const [from, to, direction] of [
        ['/library', '/library/wishlist', 'forward'],
        ['/library/lists', '/library/wishlist', 'backward'],
        ['/library/pick', '/library?status=Playing', 'backward'],
    ]) {
        const activation = route(from, to);
        for (const type of ['pageswap', 'pagereveal']) {
            const ui = setup({ activation });
            const animation = transition();
            ui.events[type]({ type, activation, viewTransition: animation });
            assert.equal(ui.dataset.libraryDirection, direction);
            assert.equal(animation.skipped, false);
            animation.finish();
            await new Promise(resolve => setImmediate(resolve));
            assert.deepEqual(ui.dataset, {});
        }
    }
});

test('same-room queries, outside destinations and missing activation never animate travel', () => {
    for (const activation of [route('/library', '/library?q=Portal'),
        route('/library', '/discover'), route('/library', 'https://example.com/library/lists'), undefined]) {
        const ui = setup();
        const animation = transition();
        ui.events.pageswap({ type: 'pageswap', activation, viewTransition: animation });
        assert.equal(animation.skipped, true);
        assert.deepEqual(ui.dataset, {});
    }
});

test('reduced motion skips travel and can stop an active camera move', () => {
    const activation = route('/library', '/library/lists');
    const reduced = setup({ reduced: true });
    const skipped = transition();
    reduced.events.pageswap({ type: 'pageswap', activation, viewTransition: skipped });
    assert.equal(skipped.skipped, true);
    const normal = setup();
    const active = transition();
    normal.events.pageswap({ type: 'pageswap', activation, viewTransition: active });
    normal.events.motion({ matches: true });
    assert.equal(active.skipped, true);
});
