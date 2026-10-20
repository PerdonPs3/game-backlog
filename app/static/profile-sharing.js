(() => {
    const username = document.querySelector('[name="username"]');
    const preview = document.querySelector('[data-profile-link-preview]');
    if (!username || !preview) return;
    const update = () => {
        preview.textContent = '/players/' + (username.value.trim().toLowerCase() || 'your_username');
    };
    username.addEventListener('input', update);
    update();
})();
