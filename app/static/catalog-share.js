(() => {
    const button = document.querySelector('[data-copy-game-link]');
    const feedback = document.querySelector('[data-copy-feedback]');
    if (!button || !feedback) return;
    let sharing = false;
    button.hidden = false;
    button.addEventListener('click', async () => {
        if (sharing) return;
        sharing = true;
        button.disabled = true;
        feedback.textContent = '';
        const url = location.origin + location.pathname;
        try {
            if (navigator.share) {
                try {
                    await navigator.share({ title: document.title, url });
                    feedback.textContent = 'Share options opened.';
                    return;
                } catch (error) {
                    if (error.name === 'AbortError') return;
                }
            }
            if (navigator.clipboard?.writeText) {
                await navigator.clipboard.writeText(url);
                feedback.textContent = 'Link copied.';
            } else {
                feedback.textContent = `Share this link: ${url}`;
            }
        } catch {
            feedback.textContent = `Copy this link from your browser to share it: ${url}`;
        } finally {
            sharing = false;
            button.disabled = false;
        }
    });
})();
