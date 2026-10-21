(() => {
    const editor = document.querySelector('[data-profile-editor]');
    if (!editor) return;
    const form = editor.querySelector('[data-profile-form]');
    const name = form.querySelector('[name="display_name"]');
    const bio = form.querySelector('[name="bio"]');
    const feedback = form.querySelector('[data-profile-feedback]');
    const save = form.querySelector('[data-save-profile]');
    const originalLabel = save.textContent;
    const previewName = editor.querySelector('[data-profile-name]');
    const previewBio = editor.querySelector('[data-profile-bio]');
    const avatar = editor.querySelector('.player-avatar');
    const color = editor.querySelector('[name="avatar_color"]');
    const photo = editor.querySelector('[name="photo"]');
    const removePhoto = editor.querySelector('[name="remove_photo"]');
    const removeButton = editor.querySelector('[data-remove-photo]');
    removeButton.type = 'button';
    const photoFeedback = editor.querySelector('[data-photo-feedback]');
    const photoPreview = editor.querySelector('[data-avatar-photo]');
    const placeholder = editor.querySelector('[data-avatar-placeholder]');
    const palette = editor.querySelector('[data-avatar-palette]');
    const savedPhoto = photoPreview.getAttribute('src');
    const avatarEditor = editor.querySelector('[data-avatar-editor]');
    const cropDialog = editor.querySelector('[data-avatar-crop]');
    const avatarTrigger = avatarEditor.querySelector('summary');
    let selectedFile = null;
    let selectedCrop = null;
    let previewUrl = null;
    const cropper = window.AvatarCrop.create(editor, (file, crop, preview) => {
        selectedFile = file;
        selectedCrop = crop;
        previewUrl = preview;
        removePhoto.value = '';
        removePhoto.disabled = true;
        updatePhoto();
        updatePreview();
        photoFeedback.textContent = 'Photo ready. Save your profile to keep this crop.';
        avatarTrigger.focus();
    }, (message) => {
        photoFeedback.textContent = message;
        avatarEditor.open = true;
    });
    for (const swatch of editor.querySelectorAll('[data-avatar-color]')) {
        swatch.addEventListener('click', () => {
            color.value = swatch.dataset.avatarColor;
            for (const option of editor.querySelectorAll('[data-avatar-color]')) option.setAttribute('aria-pressed', String(option === swatch));
            updatePreview();
        });
    }
    form.addEventListener('formdata', (event) => {
        if (selectedFile) {
            event.formData.set('photo', selectedFile, selectedFile.name);
            event.formData.set('photo_crop', JSON.stringify(selectedCrop));
        } else {
            event.formData.delete('photo');
            event.formData.delete('photo_crop');
        }
    });

    document.addEventListener('pointerdown', (event) => {
        if (!avatarEditor.contains(event.target)) avatarEditor.open = false;
    });
    avatarEditor.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && avatarEditor.open) {
            event.preventDefault();
            avatarEditor.open = false;
            avatarTrigger.focus();
        }
    });
    photo.addEventListener('invalid', () => { avatarEditor.open = true; });

    function updatePhoto() {
        photo.setCustomValidity('');
        const src = removePhoto.value === 'yes' ? null : (previewUrl || savedPhoto);
        photoPreview.hidden = !src;
        removeButton.hidden = !src;
        placeholder.hidden = Boolean(src);
        palette.hidden = Boolean(src);
        if (src) photoPreview.src = src;
        else photoPreview.removeAttribute('src');
    }
    photo.addEventListener('change', () => {
        const candidate = photo.files[0];
        photo.value = '';
        if (!candidate) return;
        avatarEditor.open = false;
        cropper.open(candidate);
    });
    removeButton.addEventListener('click', () => {
        selectedFile = selectedCrop = previewUrl = null;
        removePhoto.value = 'yes';
        removePhoto.disabled = false;
        photo.value = '';
        updatePhoto();
        updatePreview();
        photoFeedback.textContent = 'Photo removed. Save your profile to keep this change.';
        avatarTrigger.focus();
    });
    photoPreview.addEventListener('error', () => {
        photoPreview.hidden = true;
        placeholder.hidden = false;
        if (previewUrl) {
            const message = 'This photo could not be displayed. Choose another file.';
            photo.setCustomValidity(message);
            photoFeedback.textContent = message;
        }
    });
    const counter = form.querySelector('[data-bio-counter]');
    let saving = false;

    function updatePreview() {
        previewName.textContent = name.value.trim() || 'Your player name';
        previewBio.textContent = bio.value.trim() || 'Your next adventure is just the beginning.';
        counter.textContent = `${bio.value.length} / 500`;
        if (/^#[0-9a-f]{6}$/i.test(color.value)) avatar.style.setProperty('--avatar-color', color.value);
        if (!saving) {
            feedback.textContent = 'You have unsaved changes.';
            feedback.classList.remove('is-saved');
            delete feedback.dataset.saved;
        }
    }
    function onEdit(event) {
        if (event?.target === photo || cropDialog.contains(event?.target)) return;
        updatePreview();
    }
    editor.addEventListener('input', onEdit);
    editor.addEventListener('change', onEdit);
    form.addEventListener('submit', (event) => {
        if (saving) { event.preventDefault(); return; }
        saving = true;
        save.disabled = true;
        save.textContent = 'Saving…';
        form.setAttribute('aria-busy', 'true');
        feedback.classList.remove('is-saved');
        feedback.textContent = 'Saving your profile…';
    });
    window.addEventListener('pageshow', () => {
        updatePhoto();
        if (!saving) return;
        saving = false;
        save.disabled = false;
        save.textContent = originalLabel;
        form.removeAttribute('aria-busy');
        updatePreview();
    });
    updatePhoto();
    if (feedback.dataset.saved === 'true') feedback.focus({ preventScroll: true });
})();
