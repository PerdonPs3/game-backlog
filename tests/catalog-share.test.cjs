const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { runInNewContext } = require('node:vm');

function setup(writeText) {
    const events = {}, feedback = { textContent: 'Copy the address.' };
    const button = { hidden: true, addEventListener: (name, handler) => { events[name] = handler; } };
    runInNewContext(readFileSync('app/static/catalog-share.js', 'utf8'), {
        document: { querySelector: key => key === '[data-copy-game-link]' ? button : feedback },
        navigator: { clipboard: writeText ? { writeText } : undefined },
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
    assert.equal(setup().button.hidden, true);
});
