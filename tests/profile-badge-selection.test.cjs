const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {runInNewContext} = require('node:vm');

test('badge showcase is capped at three and choosing another requires deselecting one', () => {
    const node = () => ({listeners: {}, children: [], addEventListener(name, fn) { this.listeners[name] = fn; },
        append(item) { this.children.push(item); }, replaceChildren() { this.children = []; },
        setAttribute(name, value) { this[name] = value; }, focus() { this.focused = true; }});
    const badges = Array.from({length: 6}, (_, index) => ({...node(), checked: index < 3,
        setCustomValidity(message) { this.validationMessage = message; },
        closest: () => ({querySelector: selector => selector === '.achievement-emblem'
            ? {cloneNode: () => ({emblem: index})} : {firstChild: {textContent: `Badge ${index}`}}})}));
    const summary = node(), done = node(), count = {}, dialogCount = {};
    const dialog = {...node(), showModal() { this.open = true; }, close() { this.open = false; this.listeners.close(); },
        querySelector: () => done};
    const form = {querySelectorAll: () => badges, querySelector: selector => ({'[data-badge-dialog]': dialog,
        '[data-badge-summary]': summary, '[data-badge-selection-count]': count,
        '[data-badge-dialog-count]': dialogCount}[selector])};
    runInNewContext(readFileSync('app/static/profile-customization.js', 'utf8'), {
        document: {querySelector: () => form, createElement: node},
    });
    assert.equal(summary.children.length, 3);
    assert.equal(count.textContent, '3/3 featured');
    assert.equal(badges[3].disabled, true);
    assert.equal(badges[0].disabled, false);
    badges[0].checked = false; badges[0].listeners.change();
    assert.equal(badges[3].disabled, false);
    badges[3].checked = true; badges[3].listeners.change();
    assert.equal(summary.children.length, 3);
    assert.equal(badges[4].disabled, true);
    summary.children[2].listeners.click(); assert.equal(dialog.open, true);
    done.listeners.click(); assert.equal(dialog.open, false);
    assert.equal(summary.children[2].focused, true);
    badges[3].checked = false; badges[3].listeners.change();
    assert.equal(summary.children.length, 3);
    assert.equal(summary.children[2]['aria-label'], 'Add badge');
    for (const badge of badges) badge.checked = false;
    badges[0].listeners.change();
    assert.equal(summary.children.length, 3);
    assert.ok(summary.children.every(item => item['aria-label'] === 'Add badge'));
    summary.children[0].listeners.click();
    assert.equal(dialog.open, true);
});
