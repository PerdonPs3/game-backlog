const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { runInNewContext } = require('node:vm');

function setup(writeText, share) {
    const events = {}, feedback = { textContent: 'Copy the address.' };
    const button = { hidden: true, addEventListener: (name, handler) => { events[name] = handler; } };
    runInNewContext(readFileSync('app/static/catalog-share.js', 'utf8'), {
        document: { title: 'Game · Vestigium', querySelector: key => key === '[data-copy-game-link]' ? button : feedback },
        navigator: { clipboard: writeText ? { writeText } : undefined, share },
        location: { origin: 'https://example.test', pathname: '/explore/games/72', search: '?private=value', hash: '#token' },
    });
    return { button, feedback, events };
}

test('sharing copies the public game URL without query values or fragments', async () => {
    let copied;
    const { button, feedback, events } = setup(async text => { copied = text; });
    assert.equal(button.hidden, false);
    await events.click();
    assert.equal(copied, 'https://example.test/explore/games/72');
    assert.match(feedback.textContent, /Link copied/);
});

test('clipboard refusal or missing support retains a usable browser-address fallback', async () => {
    const failed = setup(async () => { throw new Error('Denied'); });
    await failed.events.click();
    assert.match(failed.feedback.textContent, /browser/);
    const unsupported = setup();
    assert.equal(unsupported.button.hidden, false);
    await unsupported.events.click();
    assert.match(unsupported.feedback.textContent, /https:\/\/example.test\/explore\/games\/72$/);
});

test('native sharing uses only the public URL and cancellation does not copy or report a failure', async () => {
    let shared, copied = false;
    const native = setup(undefined, async data => { shared = data; });
    await native.events.click();
    assert.equal(shared.url, 'https://example.test/explore/games/72');
    assert.equal(shared.title, 'Game · Vestigium');
    const cancel = setup(async () => { copied = true; }, async () => { throw { name: 'AbortError' }; });
    await cancel.events.click();
    assert.equal(copied, false);
    assert.equal(cancel.feedback.textContent, '');
    assert.equal(cancel.button.disabled, false);
});

test('a native sharing failure falls back to copying and repeated clicks do not open multiple dialogs', async () => {
    let resolve, calls = 0, copied = false;
    const pending = setup(undefined, () => { calls++; return new Promise(done => { resolve = done; }); });
    const first = pending.events.click();
    await pending.events.click();
    assert.equal(calls, 1);
    resolve();
    await first;
    const failed = setup(async () => { copied = true; }, async () => { throw new Error('Unavailable'); });
    await failed.events.click();
    assert.equal(copied, true);
    assert.equal(failed.button.disabled, false);
});
