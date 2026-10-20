const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { runInNewContext } = require('node:vm');

function setup(saved = false) {
    const events = {}, windowEvents = {}, attributes = {}, iconAttributes = {};
    const name = { value: 'Alice' }, bio = { value: '' }, selected = { value: 'controller' };
    const feedback = { textContent: 'Changes saved.', dataset: saved ? { saved: 'true' } : {},
        classList: { remove(value) { feedback.removedClass = value; } }, focus() { feedback.focused = true; } };
    const save = { textContent: 'Save changes ↗', disabled: false };
    const avatar = { dataset: {}, querySelector: () => ({ setAttribute(key, value) { iconAttributes[key] = value; } }) };
    const previewName = {}, previewBio = {}, counter = {};
    const fields = { '[name="display_name"]': name, '[name="bio"]': bio, '[name="avatar"]:checked': selected,
        '[data-profile-feedback]': feedback, '[data-save-profile]': save, '[data-bio-counter]': counter };
    const form = { querySelector: (key) => fields[key], addEventListener(key, callback) { events[key] = callback; },
        setAttribute(key, value) { attributes[key] = value; }, removeAttribute(key) { delete attributes[key]; } };
    const nodes = { '[data-profile-form]': form, '[data-profile-name]': previewName, '[data-profile-bio]': previewBio, '.player-avatar': avatar };
    const editor = { querySelector: (key) => nodes[key] };
    runInNewContext(readFileSync('app/static/profile-editor.js', 'utf8'), {
        document: { querySelector: () => editor }, window: { addEventListener(key, callback) { windowEvents[key] = callback; } },
    });
    return { name, bio, selected, feedback, save, avatar, previewName, previewBio, counter, events, windowEvents, attributes, iconAttributes };
}

test('updates the player card as text, avatar, and biography change without claiming a save', () => {
    const ui = setup(true);
    ui.name.value = '<script>Player</script>';
    ui.bio.value = 'Exploring new worlds';
    ui.selected.value = 'rocket';
    ui.events.input();
    assert.equal(ui.previewName.textContent, '<script>Player</script>');
    assert.equal(ui.previewBio.textContent, 'Exploring new worlds');
    assert.equal(ui.counter.textContent, '20 / 500');
    assert.equal(ui.iconAttributes.href, '#profile-avatar-rocket');
    assert.equal(ui.feedback.textContent, 'You have unsaved changes.');
    assert.equal(ui.feedback.dataset.saved, undefined);
});

test('shows saving and prevents duplicate submission until the browser navigates', () => {
    const ui = setup();
    let prevented = 0;
    const event = { preventDefault() { prevented++; } };
    ui.events.submit(event);
    assert.equal(ui.save.disabled, true);
    assert.equal(ui.save.textContent, 'Saving…');
    assert.equal(ui.feedback.textContent, 'Saving your profile…');
    assert.equal(ui.attributes['aria-busy'], 'true');
    ui.events.submit(event);
    assert.equal(prevented, 1);
    ui.windowEvents.pageshow();
    assert.equal(ui.save.disabled, false);
    assert.equal(ui.save.textContent, 'Save changes ↗');
    assert.equal(ui.attributes['aria-busy'], undefined);
    assert.equal(ui.feedback.textContent, 'You have unsaved changes.');
});

test('focuses only server-confirmed save feedback and handles empty preview fields', () => {
    assert.equal(setup(true).feedback.focused, true);
    const ui = setup();
    assert.equal(ui.feedback.focused, undefined);
    ui.name.value = '  ';
    ui.events.change();
    assert.equal(ui.previewName.textContent, 'Your player name');
    assert.equal(ui.previewBio.textContent, 'Your next adventure is just the beginning.');
});
