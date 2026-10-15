"use strict";

// Local synthesized effects only: no audio downloads, tracking, or dependencies.
window.createAdventureSound = (button) => {
    const Audio = window.AudioContext || window.webkitAudioContext;
    const silent = { begin() {}, stop() {}, reveal() {} };
    if (!button || !Audio) return silent;
    let context, master, frame, readPosition;
    let enabled = false, wantsSound = false, active = false, previous;
    const key = "game-backlog.roulette-sound";
    button.hidden = false;

    function label() {
        const description = enabled ? "Mute sound" : "Enable sound";
        button.setAttribute("aria-label", description);
        button.setAttribute("title", description);
        button.setAttribute("aria-pressed", String(enabled));
    }
    function remember(value) {
        try { window.localStorage.setItem(key, String(value)); } catch { /* Optional preference. */ }
    }
    function cancelFrame() {
        if (frame !== undefined) window.cancelAnimationFrame(frame);
        frame = undefined;
    }
    function tone(frequency, start, duration, type, volume) {
        if (!enabled || context?.state !== "running" || document.hidden) return;
        try {
            const oscillator = context.createOscillator();
            const gain = context.createGain();
            oscillator.type = type;
            oscillator.frequency.setValueAtTime(frequency, start);
            if (type === "square") oscillator.frequency.exponentialRampToValueAtTime(240, start + duration);
            gain.gain.setValueAtTime(0.0001, start);
            gain.gain.exponentialRampToValueAtTime(volume, start + 0.003);
            gain.gain.exponentialRampToValueAtTime(0.0001, start + duration);
            oscillator.connect(gain);
            gain.connect(master);
            oscillator.onended = () => { oscillator.disconnect(); gain.disconnect(); };
            oscillator.start(start);
            oscillator.stop(start + duration + 0.01);
        } catch { /* Audio must never interrupt the draw. */ }
    }
    function tick() {
        frame = undefined;
        if (!active || !enabled || document.hidden) return;
        const position = Math.floor(readPosition());
        if (previous !== undefined && position !== previous) {
            tone(1250, context.currentTime, 0.025, "square", 0.25);
        }
        previous = position;
        frame = window.requestAnimationFrame(tick);
    }
    function startTicks() {
        cancelFrame();
        previous = undefined;
        if (active && enabled) frame = window.requestAnimationFrame(tick);
    }
    async function activate() {
        wantsSound = true;
        try {
            if (!context) {
                context = new Audio();
                master = context.createGain();
                master.gain.value = 0.06;
                master.connect(context.destination);
            }
            // May remain suspended until this page receives a real user gesture.
            await context.resume();
            if (!wantsSound) return;
            enabled = context.state === "running";
            label();
            startTicks();
            if (enabled) tone(740, context.currentTime, 0.07, "triangle", 0.2);
        } catch {
            enabled = false;
            label();
        }
    }
    button.addEventListener("click", () => {
        if (enabled) {
            wantsSound = enabled = false;
            cancelFrame();
            context.suspend().catch(() => {});
            remember(false);
            label();
        } else {
            remember(true);
            activate();
        }
    });
    label();
    try { if (window.localStorage.getItem(key) === "true") activate(); } catch { /* Storage blocked. */ }
    window.addEventListener("pagehide", () => {
        active = wantsSound = enabled = false;
        cancelFrame();
        context?.close().catch(() => {});
    });
    return {
        begin(position) { readPosition = position; active = true; startTicks(); },
        stop() { active = false; cancelFrame(); },
        reveal() {
            active = false;
            cancelFrame();
            if (!enabled) return;
            const now = context.currentTime;
            [660, 880, 1100].forEach((frequency, index) => {
                tone(frequency, now + index * 0.065, 0.13, "triangle", 0.28);
            });
        },
    };
};
