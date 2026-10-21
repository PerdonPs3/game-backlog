const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { runInNewContext } = require('node:vm');

function setup(display = '', initial = '', readOnly = false) {
    const name = { value: display, addEventListener(_, fn) { this.input = fn; } };
    const username = { value: initial, readOnly, dataset: { reservedUsernames: '["admin","support"]' }, addEventListener(_, fn) { this.input = fn; } };
    runInNewContext(readFileSync('app/static/profile-username.js', 'utf8'), {
        document: { getElementById: id => id === 'display-name' ? name : username },
    });
    return { name, username };
}

test('suggests a valid username from display names and keeps following the name until manually edited', () => {
    const ui = setup('PerdonPs3'); assert.equal(ui.username.value, 'perdonps3');
    ui.name.value = 'Máxi Player'; ui.name.input(); assert.equal(ui.username.value, 'maxi_player');
    ui.username.value = 'chosen_name'; ui.username.input();
    ui.name.value = 'Another player'; ui.name.input(); assert.equal(ui.username.value, 'chosen_name');
});

test('handles reserved names, short names, symbols, numeric starts and length limits', () => {
    for (const name of ['admin', 'support', 'a', '123 player', '🎮', 'A'.repeat(60)]) {
        const value = setup(name).username.value;
        assert.match(value, /^[a-z][a-z0-9_]{2,23}$/);
        assert.ok(!['admin', 'support'].includes(value));
    }
    const ui = setup('Alice'); ui.name.value = ''; ui.name.input(); assert.equal(ui.username.value, '');
});

test('does not overwrite a posted username after validation or an existing readonly identity', () => {
    const ui = setup('Alice', 'already_chosen'); ui.name.value = 'New name'; ui.name.input();
    assert.equal(ui.username.value, 'already_chosen');
    const locked = setup('Alice', 'saved_identity', true); assert.equal(locked.username.value, 'saved_identity');
});
