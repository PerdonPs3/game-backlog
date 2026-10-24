/* Illustrative loops only: no requests, account reads, or writes to a real library. */
(() => {
    const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
    document.querySelectorAll('[data-product-demo]').forEach(demo => {
        const control = demo.querySelector('[data-demo-control]');
        const frames = demo.querySelectorAll('[data-demo-frame]');
        const typing = demo.querySelectorAll('[data-demo-type]');
        const stars = demo.querySelectorAll('[data-demo-stars]');
        const saved = demo.querySelector('[data-demo-saved]');
        const durations = demo.dataset.productDemo === 'library' ? [2200, 2600, 6500] : [2600, 2800, 3400];
        let step = 2, elapsed = durations[2], timer = null, visible = false, started = false, paused = false, leaving = false;
        const stop = () => { window.clearTimeout(timer); timer = null; };
        const render = () => {
            demo.dataset.step = String(step);
            demo.dataset.paused = String(paused);
            frames.forEach(frame => { frame.hidden = Number(frame.dataset.demoFrame) !== step; });
            typing.forEach(field => {
                const text = field.dataset.demoText;
                const count = motion.matches ? text.length : field.dataset.demoType === 'search'
                    ? (step === 0 ? Math.floor(elapsed / 100) : text.length)
                    : (step === 2 ? Math.floor(Math.max(0, elapsed - 1100) / 55) : 0);
                const value = text.slice(0, count);
                if (field.textContent !== value) field.textContent = value;
                field.dataset.writing = String(value.length < text.length && !paused && !motion.matches);
            });
            stars.forEach(group => {
                const value = motion.matches ? 5 : demo.dataset.productDemo === 'search'
                    ? (step === 2 ? 5 : step === 1 ? Math.min(5, Math.floor(elapsed / 280)) : 0)
                    : step === 2 ? Math.min(5, Math.floor(elapsed / 180)) : 0;
                group.dataset.rating = String(value);
            });
            if (saved) saved.dataset.saved = String(motion.matches || (step === 2 && elapsed >= 5400));
            control.textContent = paused ? 'Play ▷' : 'Pause Ⅱ';
            control.setAttribute('aria-label', `${paused ? 'Play' : 'Pause'} ${demo.dataset.productDemo} animation`);
            control.setAttribute('aria-pressed', String(paused));
        };
        const schedule = () => {
            stop();
            if (!visible || document.hidden || leaving || paused || motion.matches) return;
            timer = window.setTimeout(() => {
                elapsed += 80;
                if (elapsed >= durations[step]) { step = (step + 1) % 3; elapsed = 0; }
                render(); schedule();
            }, 80);
        };
        control.addEventListener('click', () => { paused = !paused; render(); schedule(); });
        const preference = () => {
            if (motion.matches) { stop(); step = 2; elapsed = durations[2]; }
            else if (visible && !started) { started = true; step = 0; elapsed = 0; }
            control.hidden = motion.matches;
            render(); schedule();
        };
        document.addEventListener('visibilitychange', schedule);
        window.addEventListener('pagehide', () => { leaving = true; stop(); });
        window.addEventListener('pageshow', () => { leaving = false; schedule(); });
        motion.addEventListener('change', preference);
        render(); preference();
        if ('IntersectionObserver' in window) {
            const observer = new window.IntersectionObserver(entries => {
                visible = entries[0].isIntersecting;
                if (visible && !started && !motion.matches) { started = true; step = 0; elapsed = 0; render(); }
                schedule();
            }, { threshold: .25 });
            observer.observe(demo);
        } else {
            visible = true;
            if (!motion.matches) { started = true; step = 0; elapsed = 0; render(); schedule(); }
        }
    });
})();
