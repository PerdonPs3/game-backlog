const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const { runInNewContext } = require('node:vm');
const source = readFileSync(join(__dirname, '../app/static/library-transitions.js'), 'utf8');

function setup({ reduced = false, activation, decode = () => Promise.resolve(), href = 'http://localhost/library', manualFrames = false, tabs = [] } = {}) {
    const events = {};
    const dataset = {};
    const root = { dataset };
    const destinations = [];
    const images = [];
    const frames = [];
    const motion = { matches: reduced, addEventListener: (name, fn) => events.motion = fn };
    runInNewContext(source, {
        URL,
        setTimeout, clearTimeout,
        Image: class {
            constructor() { images.push(this); }
            decode() { return decode(this.src); }
        },
        document: {
            documentElement: root,
            querySelectorAll: () => tabs,
            currentScript: { src: 'http://localhost/static/library-transitions.js' },
            addEventListener: (name, fn) => events[name] = fn,
        },
        window: {
            location: { href, origin: 'http://localhost', assign: url => destinations.push(url) },
            requestAnimationFrame: callback => manualFrames ? frames.push(callback) : setImmediate(callback),
            onpageswap: null,
            navigation: { activation },
            matchMedia: () => motion,
            addEventListener: (name, fn) => events[name] = fn,
        },
    });
    return { events, dataset, root, destinations, images, paint: () => frames.shift()?.() };
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

function click(href, overrides = {}) {
    const link = { href, hasAttribute: () => false };
    return { button: 0, prevented: false,
        target: { closest: selector => selector === '.section-navigation a' ? link : null },
        preventDefault() { this.prevented = true; }, stopImmediatePropagation() {}, ...overrides };
}

test('navigation waits for decoded artwork and preserves the full filtered destination', async () => {
    let release;
    const ui = setup({ decode: () => new Promise(resolve => release = resolve) });
    const destination = 'http://localhost/library/wishlist?from=%2Flibrary%3Fq%3DPortal';
    const event = click(destination);
    const pending = ui.events.click(event);
    assert.equal(event.prevented, true);
    assert.deepEqual(ui.destinations, []);
    release();
    await pending;
    assert.deepEqual(ui.destinations, [destination]);
    assert.equal(ui.images[0].src, 'http://localhost/static/images/backgrounds/wishlist-observatory-night.webp');
});

test('rapid clicks during artwork loading select the latest destination', async () => {
    const releases = [];
    const ui = setup({ decode: () => new Promise(resolve => releases.push(resolve)) });
    const first = ui.events.click(click('http://localhost/library/wishlist'));
    const second = ui.events.click(click('http://localhost/library/lists'));
    releases.forEach(resolve => resolve());
    await Promise.all([first, second]);
    assert.deepEqual(ui.destinations, ['http://localhost/library/lists']);
});

test('a click before the departure snapshot replaces the pending native destination', async () => {
    const ui = setup();
    await ui.events.click(click('http://localhost/library/pick'));
    await ui.events.click(click('http://localhost/library/wishlist'));
    assert.deepEqual(ui.destinations, ['http://localhost/library/pick', 'http://localhost/library/wishlist']);
});

test('rapid clicks during arrival keep only the last destination and wait for two real paints', async () => {
    const ui = setup({ activation: route('/library', '/library/wishlist'), href: 'http://localhost/library/wishlist', manualFrames: true });
    const animation = transition();
    ui.events.pagereveal({ type: 'pagereveal', viewTransition: animation });
    await ui.events.click(click('http://localhost/library/lists'));
    const event = click('http://localhost/library/pick');
    await ui.events.click(event);
    assert.equal(event.prevented, true);
    assert.deepEqual(ui.destinations, []);
    animation.finish();
    await new Promise(resolve => setImmediate(resolve));
    assert.deepEqual(ui.destinations, []);
    ui.paint();
    await new Promise(resolve => setImmediate(resolve));
    assert.deepEqual(ui.destinations, []);
    ui.paint();
    await new Promise(resolve => setImmediate(resolve));
    assert.deepEqual(ui.destinations, ['http://localhost/library/pick']);
});

test('choosing the current room during arrival cancels the queued onward trip', async () => {
    const ui = setup({ activation: route('/library', '/library/wishlist'), href: 'http://localhost/library/wishlist', manualFrames: true });
    const animation = transition();
    ui.events.pagereveal({ type: 'pagereveal', viewTransition: animation });
    await ui.events.click(click('http://localhost/library/lists'));
    await ui.events.click(click('http://localhost/library/wishlist'));
    animation.finish();
    await new Promise(resolve => setImmediate(resolve));
    ui.paint();
    ui.paint();
    await new Promise(resolve => setImmediate(resolve));
    assert.deepEqual(ui.destinations, []);
});

function tab(href, left, width = 100) {
    return { href, hasAttribute: () => false, getBoundingClientRect: () => ({ left, right: left + width, top: 190, bottom: 230, width, height: 40 }) };
}

test('snapshot-retargeted pointer clicks resolve the visible tab and preserve the last request', async () => {
    const ui = setup({ activation: route('/library', '/library/wishlist'), href: 'http://localhost/library/wishlist', manualFrames: true,
        tabs: [tab('http://localhost/library/lists', 100), tab('http://localhost/library/pick?from=%2Flibrary%3Fq%3DPortal', 200)] });
    const animation = transition();
    ui.events.pagereveal({ type: 'pagereveal', viewTransition: animation });
    for (const clientX of [150, 250]) {
        const event = click('', { type: 'click', target: ui.root, detail: 1, clientX, clientY: 210 });
        await ui.events.click(event);
        assert.equal(event.prevented, true);
    }
    assert.deepEqual(ui.destinations, []);
    animation.finish();
    await new Promise(resolve => setImmediate(resolve));
    ui.paint(); ui.paint();
    await new Promise(resolve => setImmediate(resolve));
    assert.deepEqual(ui.destinations, ['http://localhost/library/pick?from=%2Flibrary%3Fq%3DPortal']);
});

test('retarget recovery excludes non-tab areas, hidden tabs, external links and keyboard clicks', async () => {
    const ui = setup({ activation: route('/library', '/library/wishlist'), tabs: [
        tab('http://localhost/library/lists', 100, 0), tab('https://example.com/library/pick', 200), tab('http://localhost/library/pick', 300)] });
    const animation = transition();
    ui.events.pagereveal({ type: 'pagereveal', viewTransition: animation });
    for (const [clientX, clientY, detail] of [[150, 210, 1], [250, 210, 1], [350, 100, 1], [350, 210, 0]]) {
        const event = click('', { type: 'click', target: ui.root, detail, clientX, clientY });
        await ui.events.click(event);
        assert.equal(event.prevented, false);
    }
    assert.deepEqual(ui.destinations, []);
    animation.finish();
});

test('new tabs and same-room filters retain native link behavior', async () => {
    const ui = setup();
    for (const event of [click('http://localhost/library/lists', { ctrlKey: true }), click('http://localhost/library?q=Portal')]) {
        await ui.events.click(event);
        assert.equal(event.prevented, false);
    }
    assert.equal(ui.images.length, 0);
});

test('unavailable artwork never traps navigation or cancels a captured departure', async () => {
    const ui = setup({ decode: () => Promise.reject(new Error('Image unavailable')),
        activation: route('/library', '/library/lists') });
    await ui.events.click(click('http://localhost/library/lists'));
    assert.equal(ui.destinations.length, 1);
    const animation = transition();
    ui.events.pagereveal({ type: 'pagereveal', viewTransition: animation });
    assert.equal(animation.skipped, false);
    animation.finish();
});

test('a stalled image cannot leave navigation waiting indefinitely', async () => {
    const ui = setup({ decode: () => new Promise(() => {}) });
    await ui.events.click(click('http://localhost/library/wishlist'));
    assert.deepEqual(ui.destinations, ['http://localhost/library/wishlist']);
});

test('restoring a document cancels stale pending navigation and releases the departure lock', async () => {
    let release;
    const ui = setup({ decode: () => new Promise(resolve => release = resolve) });
    const waiting = ui.events.click(click('http://localhost/library/lists'));
    ui.events.pageshow();
    release();
    await waiting;
    assert.deepEqual(ui.destinations, []);
    await ui.events.click(click('http://localhost/library/lists'));
    assert.equal(ui.destinations.length, 1);
    ui.events.pageshow();
    await ui.events.click(click('http://localhost/library/lists'));
    assert.equal(ui.destinations.length, 2);
});

test('theme controls cannot cancel an active room transition', async () => {
    const ui = setup();
    const animation = transition();
    ui.events.pageswap({ type: 'pageswap', activation: route('/library', '/library/lists'), viewTransition: animation });
    const event = click('', { target: { closest: selector => selector === '[data-theme-toggle]' ? {} : null } });
    await ui.events.click(event);
    assert.equal(event.prevented, true);
    assert.equal(animation.skipped, false);
    animation.finish();
});
