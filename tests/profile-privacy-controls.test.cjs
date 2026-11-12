const {test} = require('node:test');
const assert = require('node:assert/strict');
const {runInNewContext} = require('node:vm');
const {readFileSync} = require('node:fs');

test('private profile collapses section controls without clearing their preferences', () => {
    let change;
    const master = {checked: false, addEventListener: (_, fn) => { change = fn; }};
    const sections = {hidden: false, privatePhoto: true}, note = {}, visibility = {};
    runInNewContext(readFileSync('app/static/profile-sharing.js', 'utf8'), {
        document: {querySelector: selector => ({'[data-private-profile]': master,
            '[data-privacy-sections]': sections, '[data-privacy-private-note]': note,
            '[data-privacy-visibility]': visibility}[selector])},
    });
    assert.equal(visibility.textContent, 'Public');
    master.checked = true; change();
    assert.equal(sections.hidden, true);
    assert.equal(note.hidden, false);
    assert.equal(visibility.textContent, 'Private');
    master.checked = false; change();
    assert.equal(sections.hidden, false);
    assert.equal(sections.privatePhoto, true);
});
