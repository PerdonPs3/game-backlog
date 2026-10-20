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
    const savedPhoto = photoPreview.getAttribute('src');
    const avatarEditor = editor.querySelector('[data-avatar-editor]');
    const avatarTrigger = avatarEditor.querySelector('summary');
    let previewUrl = null;

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
        if (previewUrl) URL.revokeObjectURL(previewUrl);
        previewUrl = null;
        const file = photo.files[0];
        photo.setCustomValidity('');
        photoFeedback.textContent = '';
        if (file && removePhoto.value !== 'yes') {
            if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || file.size > 2 * 1024 * 1024) {
                const message = 'Choose a JPG, PNG, or WebP photo smaller than 2 MB.';
                photo.setCustomValidity(message);
                photoFeedback.textContent = message;
            } else {
                previewUrl = URL.createObjectURL(file);
                photoFeedback.textContent = 'Preview only. Save changes to keep your photo.';
            }
        }
        const src = removePhoto.value === 'yes' ? null : (previewUrl || savedPhoto);
        photoPreview.hidden = !src;
        removeButton.hidden = !src;
        placeholder.hidden = Boolean(src);
        if (src) photoPreview.src = src;
        else photoPreview.removeAttribute('src');
    }
    photo.addEventListener('change', () => {
        removePhoto.value = '';
        removePhoto.disabled = true;
        updatePhoto();
    });
    removeButton.addEventListener('click', () => {
        removePhoto.value = 'yes';
        removePhoto.disabled = false;
        photo.value = '';
        updatePhoto();
        updatePreview();
        photoFeedback.textContent = 'Photo removed. Save your profile to keep this change.';
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
    window.addEventListener('pagehide', () => {
        if (previewUrl) URL.revokeObjectURL(previewUrl);
        previewUrl = null;
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
    editor.addEventListener('input', updatePreview);
    editor.addEventListener('change', updatePreview);
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
        if (photo.files.length) updatePhoto();
        if (!saving) return;
        saving = false;
        save.disabled = false;
        save.textContent = originalLabel;
        form.removeAttribute('aria-busy');
        updatePreview();
    });
    if (feedback.dataset.saved === 'true') feedback.focus({ preventScroll: true });
})();
