const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { runInNewContext } = require('node:vm');

function setup(saved = false, savedPhoto = null) {
    const events = {}, windowEvents = {}, documentEvents = {}, avatarEvents = {}, attributes = {}, iconAttributes = {};
    const avatarTrigger = { focus() { this.focused = true; } };
    const avatarEditor = { open: false, querySelector() { return avatarTrigger; }, contains(target) { return target === avatarTrigger; }, addEventListener(key, cb) { avatarEvents[key] = cb; } };
    const crop = { open(file) { crop.file = file; }, accept() { crop.apply(crop.file, { x: 0, y: 0, size: 200 }, 'data:image/jpeg;base64,preview'); } };
    const swatchEvents = {};
    const swatch = { dataset: { avatarColor: '#7c3aed' }, addEventListener(key, cb) { swatchEvents[key] = cb; }, setAttribute(key, value) { this[key] = value; } };
    const cropDialog = { contains() { return false; } };
    const photoEvents = {}, removeEvents = {}, imageEvents = {}, revoked = [];
    const color = { value: '#64748b' };
    const photo = { files: [], setCustomValidity(value) { this.validation = value; }, addEventListener(key, cb) { photoEvents[key] = cb; } };
    const removePhoto = { value: '', disabled: true };
    const removeButton = { hidden: true, addEventListener(key, cb) { removeEvents[key] = cb; } };
    const photoFeedback = {}, placeholder = { hidden: false }, palette = { hidden: false };
    const photoPreview = { hidden: true, getAttribute() { return savedPhoto; }, removeAttribute() { delete this.src; }, addEventListener(key, cb) { imageEvents[key] = cb; } };
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
    const nodes = { '[data-avatar-palette]': palette, '[data-profile-form]': form, '[data-profile-name]': previewName, '[data-profile-bio]': previewBio, '.player-avatar': avatar, '[data-avatar-photo]': photoPreview, '[data-avatar-placeholder]': placeholder, '[data-avatar-editor]': avatarEditor, '[data-avatar-crop]': cropDialog, ...fields };
    const editor = { querySelector: (key) => nodes[key], querySelectorAll: () => [swatch], addEventListener(key, cb) { events[key] = cb; } };
    runInNewContext(readFileSync('app/static/profile-editor.js', 'utf8'), {
        URL: { createObjectURL() { return 'blob:preview'; }, revokeObjectURL(value) { revoked.push(value); } },
        document: { querySelector: () => editor, addEventListener(key, cb) { documentEvents[key] = cb; } }, window: { AvatarCrop: { create(editor, apply, error) { crop.apply = apply; crop.error = error; return crop; } }, addEventListener(key, callback) { windowEvents[key] = callback; } },
    });
    return { palette, crop, swatch, swatchEvents, removeButton, documentEvents, avatarEvents, avatarEditor, avatarTrigger, photo, color, removePhoto, photoEvents, removeEvents, imageEvents, photoPreview, placeholder, photoFeedback, revoked, name, bio, selected, feedback, save, avatar, previewName, previewBio, counter, events, windowEvents, attributes, iconAttributes };
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
    assert.equal(ui.previewBio.textContent, '');
});


test('applies the chosen crop and restores the silhouette when removed', () => {
    const ui = setup();
    ui.photo.files = [{ type: 'image/png', size: 1000 }];
    ui.photoEvents.change();
    assert.equal(ui.photoPreview.hidden, true);
    ui.crop.accept();
    assert.equal(ui.photoPreview.src, 'data:image/jpeg;base64,preview');
    assert.equal(ui.placeholder.hidden, true);
    assert.match(ui.photoFeedback.textContent, /Photo ready/);
    assert.equal(ui.removeButton.hidden, false);
    ui.photo.files = [];
    ui.removeEvents.click();
    assert.equal(ui.removePhoto.value, 'yes');
    assert.equal(ui.removePhoto.disabled, false);
    assert.equal(ui.removeButton.hidden, true);
    assert.equal(ui.photoPreview.hidden, true);
    assert.equal(ui.placeholder.hidden, false);

});

test('a cancelled or invalid candidate leaves the previously applied crop intact', () => {
    const ui = setup();
    ui.photo.files = [{ type: 'image/png', size: 1000 }];
    ui.photoEvents.change();
    ui.crop.accept();
    ui.photo.files = [{ type: 'image/png', size: 2000 }];
    ui.photoEvents.change();
    ui.crop.error('Could not open this photo.');
    assert.equal(ui.photoPreview.src, 'data:image/jpeg;base64,preview');
    assert.equal(ui.avatarEditor.open, true);
    assert.equal(ui.photoFeedback.textContent, 'Could not open this photo.');
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
    ui.crop.accept();
    assert.equal(ui.removePhoto.value, '');
    assert.equal(ui.removePhoto.disabled, true);
    assert.equal(ui.removeButton.hidden, false);
    assert.equal(ui.photoPreview.hidden, false);
});


test('submits only the confirmed photo and crop, not an unconfirmed candidate', () => {
    const ui = setup();
    const data = new Map([['photo', 'unconfirmed']]);
    const event = { formData: { set(key, value) { data.set(key, value); }, delete(key) { data.delete(key); } } };
    ui.events.formdata(event);
    assert.equal(data.has('photo'), false);
    const file = { type: 'image/png', name: 'chosen.png', size: 1000 };
    ui.photo.files = [file];
    ui.photoEvents.change();
    ui.crop.accept();
    ui.events.formdata(event);
    assert.equal(data.get('photo'), file);
    assert.deepEqual(JSON.parse(data.get('photo_crop')), { x: 0, y: 0, size: 200 });
});

test('preset swatches update the silhouette color and selected state', () => {
    const ui = setup();
    ui.swatchEvents.click();
    assert.equal(ui.color.value, '#7c3aed');
    assert.equal(ui.swatch['aria-pressed'], 'true');
    assert.equal(ui.iconAttributes['--avatar-color'], '#7c3aed');
});

test('saved and newly confirmed photos hide colors; removing a photo restores the saved color', () => {
    const ui = setup(false, '/account/profile/photo');
    assert.equal(ui.palette.hidden, true);
    assert.equal(ui.photoPreview.hidden, false);
    ui.removeEvents.click();
    assert.equal(ui.palette.hidden, false);
    assert.equal(ui.color.value, '#64748b');
    ui.photo.files = [{ type: 'image/png', size: 1000 }];
    ui.photoEvents.change();
    assert.equal(ui.palette.hidden, false);
    ui.crop.error('Replacement cancelled.');
    assert.equal(ui.palette.hidden, false);
    ui.crop.accept();
    assert.equal(ui.palette.hidden, true);
    ui.windowEvents.pageshow();
    assert.equal(ui.palette.hidden, true);
});

test('an unconfirmed replacement never reveals colors over an existing photo', () => {
    const ui = setup(false, '/account/profile/photo');
    ui.photo.files = [{ type: 'image/png', size: 1000 }];
    ui.photoEvents.change();
    ui.crop.error('Could not open this photo.');
    assert.equal(ui.palette.hidden, true);
    assert.equal(ui.photoPreview.src, '/account/profile/photo');
});
