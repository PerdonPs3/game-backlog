(() => {
    const username = document.querySelector('[name="username"]');
    const preview = document.querySelector('[data-profile-link-preview]');
    if (!username || !preview) return;
    const update = () => {
        const path = '/profile/' + (username.value.trim().toLowerCase() || 'your_username');
        preview.textContent = path;
        if (preview.tagName === 'A') preview.setAttribute('href', path);
    };
    username.addEventListener('input', update);
    const displayName = document.querySelector('[name="display_name"]');
    displayName?.addEventListener('input', update);
    displayName?.addEventListener('change', update);
    update();
})();
