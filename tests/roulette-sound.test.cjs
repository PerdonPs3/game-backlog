const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const { runInNewContext } = require("node:vm");

function setup({ saved = null, supported = true, blocked = false, rejectResume = false } = {}) {
    const listeners = {}, frames = new Map(), tones = [], contexts = [], writes = [];
    let nextFrame = 0;
    const param = () => ({ value: 0, setValueAtTime() {}, exponentialRampToValueAtTime() {} });
    class Audio {
        constructor() { this.state = "suspended"; this.currentTime = 1; contexts.push(this); }
        createGain() { return { gain: param(), connect() {}, disconnect() {} }; }
        createOscillator() {
            const oscillator = { frequency: param(), connect() {}, disconnect() {},
                start(time) { tones.push({ type: this.type, time }); }, stop() {} };
            return oscillator;
        }
        async resume() { if (rejectResume) throw new Error("Blocked"); this.state = "running"; }
        async suspend() { this.state = "suspended"; }
        async close() { this.state = "closed"; }
    }
    const button = { attributes: {}, hidden: true,
        setAttribute(key, value) { this.attributes[key] = value; },
        addEventListener(name, callback) { this[name] = callback; },
    };
    const window = {
        AudioContext: supported ? Audio : undefined,
        localStorage: { getItem() { if (blocked) throw new Error("Blocked"); return saved; },
            setItem(key, value) { if (blocked) throw new Error("Blocked"); writes.push(value); } },
        requestAnimationFrame(callback) { frames.set(++nextFrame, callback); return nextFrame; },
        cancelAnimationFrame(id) { frames.delete(id); },
        addEventListener(name, callback) { listeners[name] = callback; },
        removeEventListener(name) { delete listeners[name]; },
    };
    const document = { hidden: false,
        addEventListener(name, callback) { listeners[name] = callback; },
        removeEventListener(name) { delete listeners[name]; },
    };
    runInNewContext(readFileSync(join(__dirname, "../app/static/roulette-sound.js"), "utf8"), { window, document });
    const sound = window.createAdventureSound(button);
    return { button, sound, frames, tones, contexts, writes, document, listeners,
        frame() { const [id, callback] = frames.entries().next().value; frames.delete(id); callback(); },
    };
}

test("sound defaults to muted without creating an audio context", () => {
    const ui = setup();
    ui.sound.begin(() => 0);
    ui.sound.reveal();
    assert.equal(ui.contexts.length, 0);
    assert.equal(ui.tones.length, 0);
    assert.equal(ui.button.attributes["aria-label"], "Enable sound");
    assert.equal(ui.button.attributes.title, "Enable sound");
    assert.equal(ui.button.hidden, false);
});

test('replacing a draw closes its audio context and removes its listeners', async () => {
    const ui = setup({ saved: 'true' });
    await Promise.resolve();
    ui.sound.begin(() => 0);
    ui.listeners['picker:replace']();
    assert.equal(ui.contexts[0].state, 'closed');
    assert.equal(ui.frames.size, 0);
    assert.equal(ui.listeners.pagehide, undefined);
    assert.equal(ui.listeners['picker:replace'], undefined);
});

test("enabled ticks follow tile crossings and the reveal plays a short chime", async () => {
    const ui = setup();
    let position = 0;
    ui.sound.begin(() => position);
    ui.button.click(); await new Promise(setImmediate);
    assert.equal(ui.button.attributes["aria-pressed"], "true");
    ui.frame();
    const initial = ui.tones.length;
    ui.frame();
    assert.equal(ui.tones.length, initial);
    position = 1.2; ui.frame();
    assert.equal(ui.tones.at(-1).type, "square");
    const ticks = ui.tones.length;
    ui.sound.reveal();
    assert.equal(ui.tones.length, ticks + 3);
    assert.equal(ui.frames.size, 0);
    assert.deepEqual(ui.writes, ["true"]);
});

test("muting cancels ticks and silences the reveal immediately", async () => {
    const ui = setup();
    ui.sound.begin(() => 0);
    ui.button.click(); await new Promise(setImmediate);
    ui.button.click();
    const count = ui.tones.length;
    ui.sound.reveal();
    assert.equal(ui.tones.length, count);
    assert.equal(ui.frames.size, 0);
    assert.equal(ui.contexts[0].state, "suspended");
    assert.equal(ui.button.attributes["aria-label"], "Enable sound");
    assert.deepEqual(ui.writes, ["true", "false"]);
});

test("saved preference resumes when allowed; storage and audio failures are harmless", async () => {
    const restored = setup({ saved: "true" }); await new Promise(setImmediate);
    assert.equal(restored.button.attributes["aria-label"], "Mute sound");
    assert.equal(restored.button.attributes.title, "Mute sound");
    const blocked = setup({ blocked: true });
    blocked.button.click(); await new Promise(setImmediate);
    assert.equal(blocked.button.attributes["aria-label"], "Mute sound");
    const rejected = setup({ rejectResume: true });
    rejected.button.click(); await new Promise(setImmediate);
    assert.equal(rejected.button.attributes["aria-label"], "Enable sound");
    assert.doesNotThrow(() => setup({ supported: false }).sound.reveal());
});

test("hidden pages stay quiet and leaving closes the audio context", async () => {
    const ui = setup();
    ui.button.click(); await new Promise(setImmediate);
    ui.sound.begin(() => 1);
    ui.document.hidden = true;
    const count = ui.tones.length;
    ui.sound.reveal();
    assert.equal(ui.tones.length, count);
    ui.listeners.pagehide();
    assert.equal(ui.contexts[0].state, "closed");
    assert.equal(ui.frames.size, 0);
});
