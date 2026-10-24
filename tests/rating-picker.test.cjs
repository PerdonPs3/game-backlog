const { test } = require('node:test');
const assert = require('node:assert/strict');
const { runInNewContext } = require('node:vm');
const { readFileSync } = require('node:fs');

test('selected, changed, cleared, and reset ratings always display on the five-star scale', () => {
    const output = {};
    let selected = '9', changed, reset, afterReset;
    const picker = {
        querySelector: selector => selector === '[data-rating-score]' ? output : { value: selected },
        addEventListener: (_, listener) => { changed = listener; },
        closest: () => ({ addEventListener: (_, listener) => { reset = listener; } }),
    };
    runInNewContext(readFileSync('app/static/rating-picker.js', 'utf8'), {
        document: { querySelectorAll: () => [picker] },
        setTimeout: callback => { afterReset = callback; },
    });
    assert.equal(output.textContent, '4.5/5');
    for (const [units, label] of [['1', '0.5/5'], ['2', '1/5'], ['5', '2.5/5'], ['10', '5/5'], ['', 'Not rated']]) {
        selected = units;
        changed();
        assert.equal(output.textContent, label);
    }
    reset();
    selected = '9';
    afterReset();
    assert.equal(output.textContent, '4.5/5');
});
