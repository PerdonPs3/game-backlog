const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { runInNewContext } = require('node:vm');

function setup() {
    const status = {};
    const slots = ['1', '2', '', '', ''].map(value => {
        const events = {}, buttons = {};
        const select = { value, get selectedOptions() { return [{ dataset: { cover: this.value ? `/cover-${this.value}.jpg` : '' } }]; }, addEventListener(key, cb) { events[key] = cb; }, focus() { this.focused = true; } };
        const image = { addEventListener(key, cb) { events[`image:${key}`] = cb; }, removeAttribute(key) { delete this[key]; } };
        for (const move of [-1, 1]) buttons[move] = { dataset: { move: String(move) }, addEventListener(key, cb) { events[`move:${move}`] = cb; } };
        return { select, image, events, querySelector: key => key === 'select' ? select : image, querySelectorAll: () => Object.values(buttons) };
    });
    const form = { querySelectorAll: () => slots, querySelector: () => status };
    runInNewContext(readFileSync('app/static/profile-showcase.js', 'utf8'), { document: { querySelector: () => form } });
    return { slots, status };
}

test('moving a pick swaps positions, refreshes both covers, and focuses its new position', () => {
    const { slots, status } = setup();
    slots[0].events['move:1']();
    assert.deepEqual(slots.map(slot => slot.select.value), ['2', '1', '', '', '']);
    assert.equal(slots[0].image.src, '/cover-2.jpg');
    assert.equal(slots[1].image.src, '/cover-1.jpg');
    assert.equal(slots[1].select.focused, true);
    assert.match(status.textContent, /Save your showcase/);
});

test('empty selections and failed covers remain usable, and edge moves do nothing', () => {
    const { slots, status } = setup();
    slots[0].events['move:-1']();
    slots[4].events['move:1']();
    assert.equal(slots[0].select.value, '1');
    slots[0].events['image:error']();
    assert.equal(slots[0].image.hidden, true);
    slots[0].select.value = '';
    slots[0].events.change();
    assert.equal(slots[0].image.src, undefined);
    assert.match(status.textContent, /unsaved/);
});
