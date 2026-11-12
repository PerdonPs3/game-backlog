const {test} = require('node:test');
const assert = require('node:assert/strict');
const {runInNewContext} = require('node:vm');
const {readFileSync} = require('node:fs');

function setup() {
    const handlers = {};
    const input = {value: '', addEventListener: (name, fn) => { handlers[name] = fn; }, focus() {}};
    const submit = {};
    const clear = {addEventListener: (name, fn) => { handlers.clear = fn; }};
    const results = {dataset: {}, setAttribute(name, value) { this[name] = value; },
        replaceChildren(...children) { this.children = children; }, animate() {}};
    const status = {};
    const form = {action: 'http://localhost/library/wishlist?page=2',
        querySelector: selector => ({'input[name="q"]': input, 'button[type="submit"]': submit,
            a: clear, div: {append() {}}, 'input[name="from"]': {value: '/library?status=Playing'}}[selector]),
        addEventListener: (name, fn) => { handlers.submit = fn; }};
    let timer;
    const requests = [], urls = [];
    runInNewContext(readFileSync('app/static/wishlist-search.js', 'utf8'), {
        document: {querySelector: selector => ({'.wishlist-search': form, '#wishlist-results': results,
            '#wishlist-search-status': status}[selector]), dispatchEvent() {}},
        window: {location: {href: form.action}, history: {replaceState: (_, __, url) => urls.push(String(url))},
            matchMedia: () => ({matches: true})},
        URL, AbortController, CustomEvent: class {},
        DOMParser: class { parseFromString(next) { return {querySelector: () => next}; } },
        setTimeout: fn => { timer = fn; }, clearTimeout: () => { timer = null; },
        fetch: (url, options) => new Promise((resolve, reject) => requests.push({url, options, resolve, reject})),
    });
    return {handlers, input, submit, clear, results, status, requests, urls,
        run: () => timer(), response: (index, count, title) => requests[index].resolve({ok: true, redirected: false,
            text: async () => ({dataset: {count: String(count)}, childNodes: [title]})})};
}

test('typing replaces results without navigation, resets paging, preserves origin, and clears', async () => {
    const ui = setup();
    assert.equal(ui.submit.hidden, true);
    ui.input.value = 'Portal';
    ui.handlers.input();
    const pending = ui.run();
    assert.equal(ui.requests[0].url.searchParams.get('q'), 'Portal');
    assert.equal(ui.requests[0].url.searchParams.has('page'), false);
    assert.equal(ui.requests[0].url.searchParams.get('from'), '/library?status=Playing');
    ui.response(0, 1, 'Portal 2');
    await pending;
    assert.equal(ui.results.children[0], 'Portal 2');
    assert.equal(ui.status.textContent, '1 game found.');
    assert.equal(ui.results['aria-busy'], 'false');
    ui.handlers.clear({preventDefault() {}});
    const cleared = ui.run();
    assert.equal(ui.input.value, '');
    assert.equal(ui.requests[1].url.searchParams.has('q'), false);
    ui.response(1, 2, 'All wishes');
    await cleared;
    assert.equal(ui.results.children[0], 'All wishes');
});

test('late responses cannot replace a newer query and failure preserves results with retry', async () => {
    const ui = setup();
    ui.input.value = 'Port'; ui.handlers.input(); const old = ui.run();
    ui.input.value = 'Elden'; ui.handlers.input(); const next = ui.run();
    assert.equal(ui.requests[0].options.signal.aborted, true);
    ui.response(1, 1, 'Elden Ring'); await next;
    ui.response(0, 1, 'Portal 2'); await old;
    assert.equal(ui.results.children[0], 'Elden Ring');
    ui.input.value = 'Dark'; ui.handlers.input(); const failed = ui.run();
    ui.requests[2].reject(new Error('offline')); await failed;
    assert.equal(ui.results.children[0], 'Elden Ring');
    assert.equal(ui.submit.hidden, false);
    assert.match(ui.status.textContent, /Try Search again/);
});
