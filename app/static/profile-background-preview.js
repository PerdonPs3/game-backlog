(() => {
    const form = document.querySelector('#profile-form');
    const cover = document.querySelector('[data-player-background]');
    if (!form || !cover) return;
    const image = cover.querySelector('[data-player-background-image]');
    const pending = form.querySelector('[data-background-preview]');
    const pendingEditor = form.querySelector('[data-background-editor]');
    function update() {
        const key = form.querySelector('[name="background_key"]:checked')?.value || 'castle';
        const removed = form.querySelector('[name="remove_background"]')?.checked;
        const choice = key === 'custom' && removed ? 'castle' : key;
        const source = choice === 'castle' ? cover.dataset.castleUrl : choice === 'custom'
            ? (!pendingEditor.hidden && pending.getAttribute('src') || cover.dataset.savedUrl) : null;
        cover.dataset.background = choice;
        image.hidden = !source;
        if (source) {
            if (image.getAttribute('src') !== source) image.src = source;
        } else image.removeAttribute('src');
    }
    form.addEventListener('change', update);
    image.addEventListener('error', () => { image.hidden = true; });
    update();
})();
