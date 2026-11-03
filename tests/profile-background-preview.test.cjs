const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {runInNewContext} = require('node:vm');

test('player card follows presets, confirmed custom crop, saved custom image, and removal', () => {
    const selected = {value: 'castle'}, remove = {checked: false};
    const pending = {getAttribute: () => 'data:image/jpeg;base64,crop'};
    const pendingEditor = {hidden: true};
    const image = {getAttribute() { return this.src; }, removeAttribute() { delete this.src; }, addEventListener() {}};
    const cover = {dataset: {castleUrl: '/castle.webp', savedUrl: '/saved-background'}, querySelector: () => image};
    let changed;
    const form = {querySelector: selector => ({'[name="background_key"]:checked': selected,
        '[name="remove_background"]': remove, '[data-background-preview]': pending,
        '[data-background-editor]': pendingEditor}[selector]), addEventListener: (_, fn) => { changed = fn; }};
    runInNewContext(readFileSync('app/static/profile-background-preview.js', 'utf8'), {
        document: {querySelector: selector => selector === '#profile-form' ? form : cover},
    });
    assert.equal(image.src, '/castle.webp');
    selected.value = 'aurora'; changed();
    assert.equal(image.hidden, true);
    assert.equal(cover.dataset.background, 'aurora');
    selected.value = 'custom'; changed();
    assert.equal(image.src, '/saved-background');
    assert.equal(image.hidden, false);
    pendingEditor.hidden = false; changed();
    assert.equal(image.src, 'data:image/jpeg;base64,crop');
    remove.checked = true; changed();
    assert.equal(image.src, '/castle.webp');
    assert.equal(cover.dataset.background, 'castle');
});
