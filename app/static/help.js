(() => {
    'use strict';
    const input = document.querySelector('[data-help-query]');
    if (!input) return;
    const topics = [...document.querySelectorAll('[data-help-topic]')];
    const empty = document.querySelector('[data-help-empty]');
    for (const video of document.querySelectorAll('[data-help-video]')) {
        const entry = video.closest('[data-help-entry]');
        const replay = entry.querySelector('[data-help-replay]');
        const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
        function load() {
            if (!video.getAttribute('src')) {
                video.src = video.dataset.src;
                video.load();
            }
        }
        function play() { load(); video.play()?.catch(() => {}); }
        replay.hidden = false;
        replay.addEventListener('click', () => { load(); video.currentTime = 0; play(); });
        entry.addEventListener('toggle', () => {
            if (!entry.open || entry.hidden) video.pause();
            else { load(); if (!reducedMotion.matches) play(); }
        });
        if (entry.open) load();
    }
    function update() {
        const query = input.value.trim().toLocaleLowerCase();
        let visible = false;
        for (const topic of topics) {
            let matches = false;
            for (const entry of topic.querySelectorAll('[data-help-entry]')) {
                entry.hidden = !entry.dataset.helpText.toLocaleLowerCase().includes(query);
                if (entry.hidden) entry.querySelector('[data-help-video]')?.pause();
                matches ||= !entry.hidden;
            }
            topic.hidden = !matches;
            visible ||= matches;
        }
        empty.hidden = visible;
    }
    input.addEventListener('input', update);
    input.form?.addEventListener('submit', event => { event.preventDefault(); update(); });
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) document.querySelectorAll('[data-help-video]').forEach(video => video.pause());
    });
    update();
})();
