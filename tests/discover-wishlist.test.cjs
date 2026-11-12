const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {join} = require('node:path');
const {runInNewContext} = require('node:vm');

function setup() {
    const handlers = {}, requests = [], navigations = [], attrs = {}, errors = [];
    const button = {textContent: '+ Add to wishlist', disabled: false};
    let replacement, focus;
    const form = {action: 'http://localhost/wishlist/games/20/add', dataset: {discoverWish: '20'},
        values: [['csrf_token', 'test-token']], contains: element => element === button,
        querySelector: selector => selector === 'button' ? button : null,
        setAttribute: (key, value) => attrs[key] = value, removeAttribute: key => delete attrs[key],
        replaceWith: value => replacement = value, append: value => errors.push(value)};
    const marker = {focus: options => focus = options};
    const document = {activeElement: button, addEventListener: (name, handler) => handlers[name] = handler,
        querySelector: selector => selector === '[data-discover-wish="20"]' ? form : null,
        createElement: () => ({dataset: {}, setAttribute() {}})};
    runInNewContext(readFileSync(join(__dirname, '../app/static/discover.js'), 'utf8'), {
        document, URL, URLSearchParams, AbortController,
        FormData: class {constructor(value) {this.values = value.values;}},
        DOMParser: class {parseFromString() {return {querySelector: () => marker};}},
        window: {location: {assign: url => navigations.push(url)}, addEventListener() {}},
        fetch: (url, options) => new Promise((resolve, reject) => requests.push({url, options, resolve, reject})),
    });
    return {button, attrs, requests, navigations, errors,
        submit() {let prevented = false; handlers.submit({target: {closest: selector => selector === '[data-discover-wish]' ? form : null}, preventDefault() {prevented = true;}}); return prevented;},
        resolve(ok = true, data = {saved: true, html: '<span>Saved</span>'}) {
            requests.at(-1).resolve({ok, redirected: false, json: async () => data});
        },
        replacement: () => replacement, focus: () => focus};
}
async function settle() {for (let i = 0; i < 12; i++) await Promise.resolve();}

test('saving posts CSRF data once and replaces only the button without navigation or scrolling focus', async () => {
    const ui = setup();
    assert.equal(ui.submit(), true); ui.submit();
    assert.equal(ui.requests.length, 1);
    assert.equal(ui.requests[0].options.method, 'POST');
    assert.deepEqual(ui.requests[0].options.body.values, [['csrf_token', 'test-token']]);
    assert.equal(ui.button.disabled, true);
    ui.resolve(); await settle();
    assert.ok(ui.replacement());
    assert.equal(ui.focus().preventScroll, true);
    assert.deepEqual(ui.navigations, []);
});

test('server and network failures preserve the action and allow retry without navigation', async () => {
    for (const network of [false, true]) {
        const ui = setup(); ui.submit();
        if (network) ui.requests[0].reject(new Error('offline'));
        else ui.resolve(false, {error: 'The catalog is busy. Please try again shortly.'});
        await settle();
        assert.equal(ui.replacement(), undefined);
        assert.equal(ui.button.disabled, false);
        assert.equal(ui.attrs['aria-busy'], undefined);
        assert.equal(ui.errors.length, 1);
        assert.deepEqual(ui.navigations, []);
        ui.submit(); assert.equal(ui.requests.length, 2);
    }
});
