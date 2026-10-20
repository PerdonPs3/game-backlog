const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { runInNewContext } = require('node:vm');

function setup(saved = false) {
    const events = {}, windowEvents = {}, documentEvents = {}, avatarEvents = {}, attributes = {}, iconAttributes = {};
    const avatarTrigger = { focus() { this.focused = true; } };
    const avatarEditor = { open: false, querySelector() { return avatarTrigger; }, contains(target) { return target === avatarTrigger; }, addEventListener(key, cb) { avatarEvents[key] = cb; } };
    const photoEvents = {}, removeEvents = {}, imageEvents = {}, revoked = [];
    const color = { value: '#64748b' };
    const photo = { files: [], setCustomValidity(value) { this.validation = value; }, addEventListener(key, cb) { photoEvents[key] = cb; } };
    const removePhoto = { value: '', disabled: true };
    const removeButton = { hidden: true, addEventListener(key, cb) { removeEvents[key] = cb; } };
    const photoFeedback = {}, placeholder = { hidden: false };
    const photoPreview = { hidden: true, getAttribute() { return null; }, removeAttribute() { delete this.src; }, addEventListener(key, cb) { imageEvents[key] = cb; } };
    const name = { value: 'Alice' }, bio = { value: '' }, selected = { value: 'controller' };
    const feedback = { textContent: 'Changes saved.', dataset: saved ? { saved: 'true' } : {},
        classList: { remove(value) { feedback.removedClass = value; } }, focus() { feedback.focused = true; } };
    const save = { textContent: 'Save changes ↗', disabled: false };
    const avatar = { style: { setProperty(key, value) { iconAttributes[key] = value; } } };
    const previewName = {}, previewBio = {}, counter = {};
    const fields = { '[name="display_name"]': name, '[name="bio"]': bio, '[name="avatar"]:checked': selected,
        '[name="avatar_color"]': color, '[name="photo"]': photo, '[name="remove_photo"]': removePhoto, '[data-remove-photo]': removeButton, '[data-photo-feedback]': photoFeedback, '[data-profile-feedback]': feedback, '[data-save-profile]': save, '[data-bio-counter]': counter };
    const form = { querySelector: (key) => fields[key], addEventListener(key, callback) { events[key] = callback; },
        setAttribute(key, value) { attributes[key] = value; }, removeAttribute(key) { delete attributes[key]; } };
    const nodes = { '[data-profile-form]': form, '[data-profile-name]': previewName, '[data-profile-bio]': previewBio, '.player-avatar': avatar, '[data-avatar-photo]': photoPreview, '[data-avatar-placeholder]': placeholder, '[data-avatar-editor]': avatarEditor, ...fields };
    const editor = { querySelector: (key) => nodes[key], addEventListener(key, cb) { events[key] = cb; } };
    runInNewContext(readFileSync('app/static/profile-editor.js', 'utf8'), {
        URL: { createObjectURL() { return 'blob:preview'; }, revokeObjectURL(value) { revoked.push(value); } },
        document: { querySelector: () => editor, addEventListener(key, cb) { documentEvents[key] = cb; } }, window: { addEventListener(key, callback) { windowEvents[key] = callback; } },
    });
    return { removeButton, documentEvents, avatarEvents, avatarEditor, avatarTrigger, photo, color, removePhoto, photoEvents, removeEvents, imageEvents, photoPreview, placeholder, photoFeedback, revoked, name, bio, selected, feedback, save, avatar, previewName, previewBio, counter, events, windowEvents, attributes, iconAttributes };
}

test('updates the player card as text, avatar, and biography change without claiming a save', () => {
    const ui = setup(true);
    ui.name.value = '<script>Player</script>';
    ui.bio.value = 'Exploring new worlds';
    ui.color.value = '#aabbcc';
    ui.events.input();
    assert.equal(ui.previewName.textContent, '<script>Player</script>');
    assert.equal(ui.previewBio.textContent, 'Exploring new worlds');
    assert.equal(ui.counter.textContent, '20 / 500');
    assert.equal(ui.iconAttributes['--avatar-color'], '#aabbcc');
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


test('previews a bounded raster upload and revokes its URL when removed', () => {
    const ui = setup();
    ui.photo.files = [{ type: 'image/png', size: 1000 }];
    ui.photoEvents.change();
    assert.equal(ui.photoPreview.src, 'blob:preview');
    assert.equal(ui.placeholder.hidden, true);
    assert.match(ui.photoFeedback.textContent, /Preview only/);
    assert.equal(ui.removeButton.hidden, false);
    ui.photo.files = [];
    ui.removeEvents.click();
    assert.equal(ui.removePhoto.value, 'yes');
    assert.equal(ui.removePhoto.disabled, false);
    assert.equal(ui.removeButton.hidden, true);
    assert.equal(ui.photoPreview.hidden, true);
    assert.equal(ui.placeholder.hidden, false);
    assert.deepEqual(ui.revoked, ['blob:preview']);
});

test('rejects oversized and unsupported files before creating a preview', () => {
    for (const file of [{ type: 'image/svg+xml', size: 100 }, { type: 'image/jpeg', size: 3 * 1024 * 1024 }]) {
        const ui = setup();
        ui.photo.files = [file];
        ui.photoEvents.change();
        assert.match(ui.photo.validation, /smaller than 2 MB/);
        assert.equal(ui.photoPreview.hidden, true);
    }
});


test('Escape closes avatar options and restores keyboard focus to the picture', () => {
    const ui = setup();
    ui.avatarEditor.open = true;
    let prevented = false;
    ui.avatarEvents.keydown({ key: 'Escape', preventDefault() { prevented = true; } });
    assert.equal(ui.avatarEditor.open, false);
    assert.equal(ui.avatarTrigger.focused, true);
    assert.equal(prevented, true);
});

test('outside pointer closes options while interacting inside keeps them open', () => {
    const ui = setup();
    ui.avatarEditor.open = true;
    ui.documentEvents.pointerdown({ target: ui.avatarTrigger });
    assert.equal(ui.avatarEditor.open, true);
    ui.documentEvents.pointerdown({ target: {} });
    assert.equal(ui.avatarEditor.open, false);
});

test('invalid upload opens its options so the browser can show the validation error', () => {
    const ui = setup();
    ui.photoEvents.invalid();
    assert.equal(ui.avatarEditor.open, true);
});


test('remove action is absent without a photo and a replacement cancels pending removal', () => {
    const ui = setup();
    assert.equal(ui.removeButton.hidden, true);
    ui.removeEvents.click();
    ui.photo.files = [{ type: 'image/png', size: 1000 }];
    ui.photoEvents.change();
    assert.equal(ui.removePhoto.value, '');
    assert.equal(ui.removePhoto.disabled, true);
    assert.equal(ui.removeButton.hidden, false);
    assert.equal(ui.photoPreview.hidden, false);
});
