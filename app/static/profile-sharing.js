(() => {
    const privateProfile = document.querySelector('[data-private-profile]');
    if (privateProfile) {
        const sections = document.querySelector('[data-privacy-sections]');
        const note = document.querySelector('[data-privacy-private-note]');
        const visibility = document.querySelector('[data-privacy-visibility]');
        const updatePrivacy = () => {
            sections.hidden = privateProfile.checked;
            note.hidden = !privateProfile.checked;
            visibility.textContent = privateProfile.checked ? 'Private' : 'Public';
        };
        privateProfile.addEventListener('change', updatePrivacy);
        updatePrivacy();
    }
    const username = document.querySelector('[name="username"]');
    const preview = document.querySelector('[data-profile-link-preview]');
    if (!username || !preview) return;
    const update = () => {
        const path = '/players/' + (username.value.trim().toLowerCase() || 'your_username');
        preview.textContent = path;
        if (preview.tagName === 'A') preview.setAttribute('href', path);
    };
    username.addEventListener('input', update);
    const displayName = document.querySelector('[name="display_name"]');
    displayName?.addEventListener('input', update);
    displayName?.addEventListener('change', update);
    update();
})();
