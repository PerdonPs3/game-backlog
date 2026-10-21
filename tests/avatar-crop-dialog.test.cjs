const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { runInNewContext } = require('node:vm');

function setup() {
    const revoked = [], applied = [], errors = [], draws = [], images = [], imagePlans = [];
    function element(extra = {}) { return { events: {}, addEventListener(name, fn) { this.events[name] = fn; }, focus() {}, ...extra }; }
    const context = { fillRect() {}, drawImage(...args) { draws.push(args); } };
    const nodes = Object.fromEntries(['stage','zoom','error','apply','reset','cancel','replace','replacement'].map(name => [`[data-crop-${name}]`, element()]));
    nodes['[data-crop-replacement]'].files = [];
    nodes['[data-crop-replacement]'].click = function () { this.clicked = true; };
    nodes['[data-crop-canvas]'] = { getContext: () => context };
    const dialog = element({ open: false, querySelector: selector => nodes[selector],
        showModal() { this.open = true; }, close() { this.open = false; this.events.close(); } });
    const module = { exports: {} };
    let next = 0;
    runInNewContext(readFileSync('app/static/avatar-crop.js', 'utf8'), {
        module,
        Image: class { constructor() { this.naturalWidth = 400; this.naturalHeight = 200; Object.assign(this, imagePlans.shift()); images.push(this); }
            decode() { return this.decodePromise || (this.fail ? Promise.reject(new Error()) : Promise.resolve()); } },
        URL: { createObjectURL: () => `blob:${++next}`, revokeObjectURL: url => revoked.push(url) },
        document: { createElement: () => ({ getContext: () => context, toDataURL: () => 'data:preview' }) },
    });
    const editor = { querySelector: selector => selector === '[data-avatar-crop]' ? dialog : element() };
    const crop = module.exports.create(editor, (...values) => applied.push(values), message => errors.push(message));
    return { crop, dialog, nodes, revoked, applied, errors, draws, images, imagePlans };
}
const photo = name => ({ name, type: 'image/png', size: 1000 });

test('the paperclip opens the picker and a valid replacement becomes the applied image', async () => {
    const ui = setup(); await ui.crop.open(photo('first.png'));
    ui.nodes['[data-crop-replace]'].events.click();
    assert.equal(ui.nodes['[data-crop-replacement]'].clicked, true);
    const second = photo('second.png');
    ui.nodes['[data-crop-replacement]'].files = [second];
    await ui.nodes['[data-crop-replacement]'].events.change();
    assert.equal(ui.dialog.open, true);
    assert.ok(ui.revoked.includes('blob:1'));
    ui.nodes['[data-crop-apply]'].events.click();
    assert.equal(ui.applied[0][0], second);
    assert.equal(ui.dialog.open, false);
});

test('cancelling the picker or choosing an invalid replacement preserves the current crop', async () => {
    const ui = setup(), first = photo('first.png'); await ui.crop.open(first);
    ui.nodes['[data-crop-replacement]'].events.change();
    await ui.crop.open({ type: 'image/svg+xml', size: 100 });
    assert.equal(ui.dialog.open, true); assert.equal(ui.errors.length, 0);
    assert.match(ui.nodes['[data-crop-error]'].textContent, /JPG, PNG, or WebP/);
    assert.equal(ui.revoked.length, 0);
    ui.nodes['[data-crop-apply]'].events.click();
    assert.equal(ui.applied[0][0], first);
});

test('cancelling the dialog never applies an unconfirmed replacement', async () => {
    const ui = setup(); await ui.crop.open(photo('first.png')); await ui.crop.open(photo('second.png'));
    ui.nodes['[data-crop-cancel]'].events.click();
    assert.equal(ui.applied.length, 0); assert.equal(ui.dialog.open, false);
    assert.deepEqual(ui.revoked, ['blob:1', 'blob:2']);
});

test('a decode failure preserves the previous image and reports the error inside the dialog', async () => {
    const ui = setup(), first = photo('first.png'); await ui.crop.open(first);
    ui.imagePlans.push({ fail: true }); await ui.crop.open(photo('broken.png'));
    assert.equal(ui.dialog.open, true); assert.equal(ui.errors.length, 0);
    assert.match(ui.nodes['[data-crop-error]'].textContent, /could not be opened/);
    ui.nodes['[data-crop-apply]'].events.click(); assert.equal(ui.applied[0][0], first);
});

test('closing during replacement decoding cannot reopen the dialog later', async () => {
    const ui = setup(); await ui.crop.open(photo('first.png'));
    let resolve; ui.imagePlans.push({ decodePromise: new Promise(done => { resolve = done; }) });
    const pending = ui.crop.open(photo('pending.png'));
    ui.nodes['[data-crop-cancel]'].events.click(); resolve(); await pending;
    assert.equal(ui.dialog.open, false); assert.equal(ui.applied.length, 0);
    assert.ok(ui.revoked.includes('blob:2'));
});
