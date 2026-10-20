(() => {
    const portrait = document.querySelector('.profile-portrait img');
    if (!portrait) return;
    portrait.addEventListener('error', () => portrait.remove(), { once: true });
    if (portrait.complete && portrait.naturalWidth === 0) portrait.remove();
})();
