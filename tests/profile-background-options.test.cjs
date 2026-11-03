const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {runInNewContext} = require('node:vm');

function setup(hash = '') {
    const node = () => ({listeners: {}, addEventListener(name, fn) { this.listeners[name] = fn; }});
    const trigger = {...node(), focus() { this.focused = true; }};
    const upload = node(), adjust = node(), done = node();
    const field = {querySelector: selector => selector === '[name="background"]' ? upload : adjust};
    const body = {append(value) { this.child = value; }};
    const crop = {open: false};
    const dialog = {...node(), open: false, showModal() { this.open = true; },
        close() { this.open = false; this.listeners.close(); },
        querySelector: selector => selector === '[data-background-options-body]' ? body : done};
    runInNewContext(readFileSync('app/static/profile-background-options.js', 'utf8'), {
        document: {querySelector: selector => ({'[data-edit-background]': trigger,
            '[data-background-options]': dialog, '#profile-background': field, '[data-background-dialog]': crop}[selector])},
        window: {location: {hash}},
    });
    return {trigger, dialog, field, body, done, upload, adjust};
}

test('visible card control opens options, Done restores focus, and upload yields to cropping', () => {
    const ui = setup();
    assert.equal(ui.body.child, ui.field);
    assert.equal(ui.dialog.open, false);
    ui.trigger.listeners.click({preventDefault() {}});
    assert.equal(ui.dialog.open, true);
    ui.done.listeners.click();
    assert.equal(ui.trigger.focused, true);
    ui.trigger.listeners.click({preventDefault() {}});
    ui.upload.listeners.change();
    assert.equal(ui.dialog.open, false);
});

test('profile background anchor opens the same options directly', () => {
    assert.equal(setup('#profile-background').dialog.open, true);
});
