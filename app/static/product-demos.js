/* Illustrations only: these sequences never read or change a player's data. */
(() => {
    const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
    document.querySelectorAll('[data-product-demo]').forEach(demo => {
        const control = demo.querySelector('[data-demo-control]');
        const frames = demo.querySelectorAll('[data-demo-frame]');
        let step = 2, timer = null, visible = false, started = false, paused = false;
        const render = () => {
            demo.dataset.step = String(step);
            frames.forEach(frame => { frame.hidden = Number(frame.dataset.demoFrame) !== step; });
            control.textContent = step === 2 ? 'Replay ↻' : paused ? 'Play ▷' : 'Pause Ⅱ';
            control.setAttribute('aria-label', `${step === 2 ? 'Replay' : paused ? 'Play' : 'Pause'} ${demo.dataset.productDemo} demo`);
        };
        const stop = () => { window.clearTimeout(timer); timer = null; };
        const schedule = () => {
            stop();
            if (!visible || document.hidden || paused || motion.matches || step === 2) return;
            timer = window.setTimeout(() => { step += 1; render(); schedule(); }, 2400);
        };
        control.addEventListener('click', () => {
            if (step === 2) { step = 0; paused = false; }
            else paused = !paused;
            render(); schedule();
        });
        const preference = () => {
            if (motion.matches) { stop(); step = 2; control.hidden = true; render(); }
            else { control.hidden = false; schedule(); }
        };
        document.addEventListener('visibilitychange', schedule);
        window.addEventListener('pagehide', stop);
        window.addEventListener('pageshow', schedule);
        motion.addEventListener('change', preference);
        render(); preference();
        if ('IntersectionObserver' in window) {
            const observer = new window.IntersectionObserver(entries => {
                visible = entries[0].isIntersecting;
                if (visible && !started && !motion.matches) { started = true; step = 0; render(); }
                schedule();
            }, { threshold: .35 });
            observer.observe(demo);
        } else visible = true;
    });
})();
