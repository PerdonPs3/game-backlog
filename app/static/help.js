(() => {
    'use strict';
    const input = document.querySelector('[data-help-query]');
    if (!input) return;
    const topics = [...document.querySelectorAll('[data-help-topic]')];
    const empty = document.querySelector('[data-help-empty]');
    const stopDemos = new Map();
    for (const video of document.querySelectorAll('[data-help-video]')) {
        const entry = video.closest('[data-help-entry]');
        const replay = entry.querySelector('[data-help-replay]');
        const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
        const answer = entry.querySelector('.help-answer');
        let startTimer = null;
        let openingAnimation;
        function cancelStart() { clearTimeout(startTimer); startTimer = null; }
        function stop() { cancelStart(); video.pause(); }
        stopDemos.set(video, stop);
        function load() {
            if (!video.getAttribute('src')) {
                video.src = video.dataset.src;
                video.load();
            }
        }
        function play() { load(); video.play()?.catch(() => {}); }
        replay.hidden = false;
        video.addEventListener('play', () => {
            cancelStart();
            stopDemos.forEach((stop, other) => { if (other !== video) stop(); });
        });
        replay.addEventListener('click', () => { cancelStart(); load(); video.currentTime = 0; play(); });
        entry.addEventListener('toggle', () => {
            stop();
            openingAnimation?.cancel();
            if (!entry.open || entry.hidden) return;
            stopDemos.forEach((stop, other) => { if (other !== video) stop(); });
            load();
            if (reducedMotion.matches) return;
            openingAnimation = answer?.animate?.([
                {height:'0px', opacity:0, transform:'translateY(6px)'},
                {height:`${answer.scrollHeight}px`, opacity:1, transform:'translateY(0)'},
            ], {duration:380, easing:'cubic-bezier(.2,.8,.2,1)'});
            startTimer = setTimeout(() => {
                startTimer = null;
                if (entry.open && !entry.hidden && !document.hidden && !reducedMotion.matches) play();
            }, 2000);
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
                if (entry.hidden) stopDemos.get(entry.querySelector('[data-help-video]'))?.();
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
        if (document.hidden) stopDemos.forEach(stop => stop());
    });
    update();
})();
