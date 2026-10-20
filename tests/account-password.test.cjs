const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { runInNewContext } = require('node:vm');
const { join } = require('node:path');

function setup() {
    const events = {}, formEvents = {};
    function input(id) {
        return { id, value: '', type: 'password', events: {},
            addEventListener(event, fn) { this.events[event] = fn; },
            setCustomValidity(text) { this.validityMessage = text; } };
    }
    const password = input('password'), confirmation = input('confirmation');
    const elements = { password, confirmation, 'password-count': {}, 'confirmation-feedback': { textContent: '' } };
    password.form = { addEventListener(event, fn) { formEvents[event] = fn; } };
    const buttons = ['password', 'confirmation'].map(id => ({
        hidden: true, dataset: { passwordToggle: id }, slash: { hidden: true, toggleAttribute(_, value) { this.hidden = value; } }, attributes: {},
        addEventListener(_, fn) { this.click = fn; },
        setAttribute(name, value) { this.attributes[name] = value; },
        querySelector() { return this.slash; },
    }));
    runInNewContext(readFileSync(join(__dirname, '../app/static/account-password.js'), 'utf8'), {
        document: { getElementById: id => elements[id], querySelectorAll: () => buttons },
        window: { addEventListener(event, fn) { events[event] = fn; }, setTimeout: fn => fn() },
    });
    return { password, confirmation, buttons, elements, events, formEvents };
}

test('counts characters, enforces the minimum, and clears errors as the user corrects them', () => {
    const ui = setup();
    ui.password.value = '1234567'; ui.password.events.input();
    assert.match(ui.elements['password-count'].textContent, /^7 characters/);
    assert.equal(ui.password.validityMessage, 'Use 8 to 128 characters.');
    ui.password.value = 'longer-than-eight'; ui.password.events.input();
    assert.equal(ui.password.validityMessage, '');
    ui.confirmation.value = 'other-password'; ui.confirmation.events.input();
    assert.equal(ui.confirmation.validityMessage, 'Passwords do not match.');
    ui.confirmation.value = ui.password.value; ui.confirmation.events.input();
    assert.equal(ui.confirmation.validityMessage, '');
    assert.equal(ui.elements['confirmation-feedback'].textContent, 'Passwords match.');
    ui.password.value += '!'; ui.password.events.input();
    assert.equal(ui.confirmation.validityMessage, 'Passwords do not match.');
});

test('each eye controls only its own input and passwords are hidden on leaving or submitting', () => {
    const ui = setup();
    assert.equal(ui.buttons[0].hidden, false);
    ui.buttons[0].click(); assert.equal(ui.password.type, 'text');
    assert.equal(ui.buttons[0].slash.hidden, false);
    assert.equal(ui.confirmation.type, 'password');
    assert.equal(ui.buttons[0].attributes['aria-pressed'], 'true');
    ui.buttons[1].click(); assert.equal(ui.confirmation.type, 'text');
    ui.events.pagehide(); assert.equal(ui.password.type, 'password');
    assert.equal(ui.confirmation.type, 'password');
    ui.buttons[0].click(); ui.formEvents.submit(); assert.equal(ui.password.type, 'password');
});

test('counts Unicode code points consistently with server validation and refreshes autofilled values', () => {
    const ui = setup(); ui.password.value = '🎮'.repeat(8); ui.events.pageshow();
    assert.match(ui.elements['password-count'].textContent, /^8 characters/);
    assert.equal(ui.password.validityMessage, '');
    ui.password.value = 'x'.repeat(129); ui.password.events.input();
    assert.equal(ui.password.validityMessage, 'Use 8 to 128 characters.');
});
