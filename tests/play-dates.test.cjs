const { test } = require('node:test');
const assert = require('node:assert/strict');
const { dateValue } = require('../app/static/play-dates.js');

test('optional date parts produce the existing ISO date values without timezone conversion', () => {
    assert.deepEqual(dateValue('', '', ''), { value: '', error: '' });
    assert.deepEqual(dateValue('15', '7', '2026'), { value: '2026-07-15', error: '' });
    assert.equal(dateValue('1', '1', '0042').value, '0042-01-01');
    assert.equal(dateValue('31', '12', '9999').value, '9999-12-31');
});

test('partial dates, impossible days and invalid numeric input cannot silently become other dates', () => {
    for (const parts of [['', '3', '2026'], ['31', '4', '2026'], ['0', '1', '2026'], ['1', '13', '2026'], ['1', '1', '0'], ['1', '1', '26'], ['1', '1', '10000'], ['1e1', '1', '2026'], ['1.5', '1', '2026']]) {
        const result = dateValue(...parts);
        assert.equal(result.value, '');
        assert.ok(result.error);
    }
});

test('leap years follow Gregorian century rules', () => {
    assert.equal(dateValue('29', '2', '2024').value, '2024-02-29');
    assert.equal(dateValue('29', '2', '2000').value, '2000-02-29');
    assert.ok(dateValue('29', '2', '1900').error);
    assert.ok(dateValue('29', '2', '2026').error);
});
