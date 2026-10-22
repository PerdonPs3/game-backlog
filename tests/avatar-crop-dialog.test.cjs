const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { runInNewContext } = require('node:vm');

function setup() {
    const revoked = [], applied = [], errors = [], draws = [], images = [], imagePlans = [], canvases = [], blobPlans = [];
    function element(extra = {}) { return { events: {}, addEventListener(name, fn) { this.events[name] = fn; }, focus() {}, ...extra }; }
    const context = { fillRect() {}, drawImage(...args) { draws.push(args); } };
    const nodes = Object.fromEntries(['stage','zoom','status','error','apply','reset','cancel','replace','replacement'].map(name => [`[data-crop-${name}]`, element()]));
    nodes['[data-crop-replacement]'].files = [];
    nodes['[data-crop-replacement]'].click = function () { this.clicked = true; };
    nodes['[data-crop-canvas]'] = { getContext: () => context };
    const dialog = element({ open: false, querySelector: selector => nodes[selector],
        showModal() { this.open = true; }, close() { this.open = false; this.events.close(); } });
    const module = { exports: {} };
    let next = 0;
    runInNewContext(readFileSync('app/static/avatar-crop.js', 'utf8'), {
        module,
        File: class { constructor(parts, name, options) { this.name = name; this.type = options.type; this.size = parts[0].size; } },
        Image: class { constructor() { this.naturalWidth = 400; this.naturalHeight = 200; Object.assign(this, imagePlans.shift()); images.push(this); }
            decode() { return this.decodePromise || (this.fail ? Promise.reject(new Error()) : Promise.resolve()); } },
        URL: { createObjectURL: () => `blob:${++next}`, revokeObjectURL: url => revoked.push(url) },
        document: { createElement: () => {
            const canvas = { getContext: () => context, toDataURL: () => 'data:preview',
                toBlob(callback, type, quality) {
                    this.quality = quality;
                    const result = blobPlans.length ? blobPlans.shift() : { size: 100000 };
                    if (typeof result === 'function') result(callback);
                    else callback(result);
                } };
            canvases.push(canvas); return canvas;
        } },
    });
    const editor = { querySelector: selector => selector === '[data-avatar-crop]' ? dialog : element() };
    const crop = module.exports.create(editor, (...values) => applied.push(values), message => errors.push(message));
    return { crop, dialog, nodes, revoked, applied, errors, draws, images, imagePlans, canvases, blobPlans };
}
const photo = name => ({ name, type: 'image/png', size: 1000 });

test('large photos are resized proportionally and only the optimized JPEG and its crop are applied', async () => {
    const ui = setup();
    ui.imagePlans.push({ naturalWidth: 4000, naturalHeight: 2000 });
    await ui.crop.open({ ...photo('large.png'), size: 3 * 1024 * 1024 });
    assert.equal(ui.dialog.open, true);
    assert.equal(ui.canvases[0].width, 2048);
    assert.equal(ui.canvases[0].height, 1024);
    assert.equal(ui.canvases[0].quality, 0.9);
    ui.nodes['[data-crop-apply]'].events.click();
    const [file, crop] = ui.applied[0];
    assert.equal(file.type, 'image/jpeg');
    assert.equal(file.name, 'profile-photo.jpg');
    assert.ok(file.size <= 2 * 1024 * 1024);
    assert.equal(crop.x, 512);
    assert.equal(crop.y, 0);
    assert.equal(crop.size, 1024);
});

test('compression retries lower quality and preserves the previous crop when encoding fails', async () => {
    const ui = setup(), first = photo('first.png');
    await ui.crop.open(first);
    ui.blobPlans.push({ size: 3 * 1024 * 1024 }, null);
    await ui.crop.open({ ...photo('large.png'), size: 3 * 1024 * 1024 });
    assert.equal(ui.canvases[0].quality, 0.75);
    assert.match(ui.nodes['[data-crop-error]'].textContent, /could not be prepared/);
    ui.nodes['[data-crop-apply]'].events.click();
    assert.equal(ui.applied[0][0], first);
});

test('cancelling during compression discards the eventual result', async () => {
    const ui = setup(); let finish, started;
    const preparing = new Promise(resolve => { started = resolve; });
    ui.blobPlans.push(callback => { finish = callback; started(); });
    const pending = ui.crop.open({ ...photo('large.png'), size: 3 * 1024 * 1024 });
    await preparing;
    assert.equal(typeof finish, 'function');
    ui.nodes['[data-crop-cancel]'].events.click();
    finish({ size: 1000 }); await pending;
    assert.equal(ui.dialog.open, false);
    assert.equal(ui.applied.length, 0);
    assert.ok(ui.revoked.includes('blob:1'));
});

test('images over the pixel bound are rejected before allocating an optimization canvas', async () => {
    const ui = setup();
    ui.imagePlans.push({ naturalWidth: 8000, naturalHeight: 8000 });
    await ui.crop.open(photo('huge.png'));
    assert.equal(ui.canvases.length, 0);
    assert.equal(ui.nodes['[data-crop-apply]'].disabled, true);
    assert.match(ui.nodes['[data-crop-error]'].textContent, /32 million pixels/);
});

test('the first selection opens immediately while decoding and can be cancelled', async () => {
    const ui = setup();
    let resolve;
    ui.imagePlans.push({ decodePromise: new Promise(done => { resolve = done; }) });
    const pending = ui.crop.open(photo('first.png'));
    assert.equal(ui.dialog.open, true);
    assert.equal(ui.nodes['[data-crop-apply]'].disabled, true);
    assert.equal(ui.nodes['[data-crop-status]'].textContent, 'Opening photo…');
    ui.nodes['[data-crop-cancel]'].events.click();
    resolve(); await pending;
    assert.equal(ui.dialog.open, false);
    assert.equal(ui.applied.length, 0);
});

test('oversized initial files show an actionable error in the open editor', async () => {
    const ui = setup();
    await ui.crop.open({ ...photo('large.png'), size: 21 * 1024 * 1024 });
    assert.equal(ui.dialog.open, true);
    assert.equal(ui.nodes['[data-crop-apply]'].disabled, true);
    assert.match(ui.nodes['[data-crop-error]'].textContent, /up to 20 MB/);
    assert.equal(ui.nodes['[data-crop-status]'].textContent, '');
    await ui.crop.open(photo('smaller.png'));
    assert.equal(ui.nodes['[data-crop-apply]'].disabled, false);
    assert.equal(ui.nodes['[data-crop-error]'].textContent, '');
    ui.nodes['[data-crop-apply]'].events.click();
    assert.equal(ui.applied[0][0].name, 'smaller.png');
});

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
    assert.match(ui.nodes['[data-crop-error]'].textContent, /could not be prepared/);
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
