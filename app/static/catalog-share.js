(() => {
    const button = document.querySelector('[data-copy-game-link]');
    const feedback = document.querySelector('[data-copy-feedback]');
    if (!button || !feedback || !navigator.clipboard?.writeText) return;
    button.hidden = false;
    button.addEventListener('click', async () => {
        try {
            await navigator.clipboard.writeText(location.origin + location.pathname);
            feedback.textContent = 'Link copied.';
        } catch {
            feedback.textContent = "Copy this page's address from your browser to share it.";
        }
    });
})();
