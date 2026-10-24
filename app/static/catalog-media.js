/* Load a video player only after an explicit play action. Switching stops it. */
(() => {
    document.querySelectorAll('[data-media-gallery]').forEach(gallery => {
        const items = [...gallery.querySelectorAll('[data-media-item]')];
        if (!items.length) return;
        const stage = gallery.querySelector('[data-media-stage]');
        const poster = gallery.querySelector('[data-media-poster]');
        const play = gallery.querySelector('[data-media-play]');
        const caption = gallery.querySelector('[data-media-caption]');
        const position = gallery.querySelector('[data-media-position]');
        const external = gallery.querySelector('[data-media-external]');
        const previewCache = new Map();
        let selected = items[0];
        let selectionVersion = 0;
        function upgradePreview(item, version) {
            const id = item.dataset.mediaId;
            if (!/^[A-Za-z0-9_-]{11}$/.test(id)) return;
            if (previewCache.has(id)) {
                poster.src = previewCache.get(id);
                return;
            }
            const sizes = ['maxresdefault', 'sddefault'];
            function trySize(index) {
                if (version !== selectionVersion) return;
                if (index === sizes.length) {
                    previewCache.set(id, item.dataset.preview);
                    return;
                }
                const candidate = new Image();
                candidate.referrerPolicy = 'no-referrer';
                candidate.onload = () => {
                    // Missing YouTube sizes can return a tiny placeholder with HTTP 200.
                    if (candidate.naturalWidth < 480) { trySize(index + 1); return; }
                    previewCache.set(id, candidate.src);
                    if (version === selectionVersion) poster.src = candidate.src;
                };
                candidate.onerror = () => trySize(index + 1);
                candidate.src = `https://i.ytimg.com/vi/${id}/${sizes[index]}.jpg`;
            }
            trySize(0);
        }
        function select(item) {
            stage.querySelector('iframe')?.remove();
            selected = item;
            const version = ++selectionVersion;
            items.forEach(option => {
                if (option === item) option.setAttribute('aria-current', 'true');
                else option.removeAttribute('aria-current');
            });
            const video = item.dataset.kind === 'video';
            stage.dataset.kind = item.dataset.kind;
            poster.src = video ? item.dataset.preview : item.href;
            if (video) upgradePreview(item, version);
            poster.alt = item.dataset.title;
            poster.hidden = false;
            play.hidden = !video;
            play.setAttribute('aria-label', `Play ${item.dataset.title}`);
            caption.textContent = item.dataset.title;
            position.textContent = `${items.indexOf(item) + 1} / ${items.length}`;
            external.href = item.href;
            external.textContent = video ? 'Watch on YouTube ↗' : 'Open image ↗';
        }
        items.forEach(item => item.addEventListener('click', event => {
            if (event.button || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
            event.preventDefault();
            select(item);
        }));
        play.addEventListener('click', () => {
            const id = selected.dataset.mediaId;
            if (selected.dataset.kind !== 'video' || !/^[A-Za-z0-9_-]{11}$/.test(id)) return;
            const frame = document.createElement('iframe');
            frame.src = `https://www.youtube-nocookie.com/embed/${id}?autoplay=1&playsinline=1&rel=0`;
            frame.title = selected.dataset.title;
            frame.allow = 'autoplay; encrypted-media; picture-in-picture; fullscreen';
            frame.allowFullscreen = true;
            frame.referrerPolicy = 'strict-origin-when-cross-origin';
            stage.querySelector('iframe')?.remove();
            stage.append(frame);
            poster.hidden = true;
            play.hidden = true;
            frame.focus();
        });
        select(selected);
    });
})();
