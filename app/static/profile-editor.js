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
    const avatarIcon = avatar.querySelector('use');
    const counter = form.querySelector('[data-bio-counter]');
    let saving = false;

    function updatePreview() {
        previewName.textContent = name.value.trim() || 'Your player name';
        previewBio.textContent = bio.value.trim() || 'Your next adventure is just the beginning.';
        counter.textContent = `${bio.value.length} / 500`;
        const selected = form.querySelector('[name="avatar"]:checked');
        if (selected && ['controller', 'star', 'ghost', 'rocket'].includes(selected.value)) {
            avatarIcon.setAttribute('href', `#profile-avatar-${selected.value}`);
            avatar.dataset.avatar = selected.value;
        }
        if (!saving) {
            feedback.textContent = 'You have unsaved changes.';
            feedback.classList.remove('is-saved');
            delete feedback.dataset.saved;
        }
    }
    form.addEventListener('input', updatePreview);
    form.addEventListener('change', updatePreview);
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
        if (!saving) return;
        saving = false;
        save.disabled = false;
        save.textContent = originalLabel;
        form.removeAttribute('aria-busy');
        updatePreview();
    });
    if (feedback.dataset.saved === 'true') feedback.focus({ preventScroll: true });
})();
