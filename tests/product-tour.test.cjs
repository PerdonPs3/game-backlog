const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { runInNewContext } = require('node:vm');
const { join } = require('node:path');

function setup() {
    let focused;
    const tabs = [0, 1, 2].map(index => ({
        id: `tab-${index}`, attributes: {}, events: {},
        setAttribute(key, value) { this.attributes[key] = value; },
        addEventListener(key, callback) { this.events[key] = callback; },
        focus() { focused = index; },
    }));
    const panels = tabs.map(() => ({ hidden: false, attributes: {}, setAttribute(key, value) { this.attributes[key] = value; } }));
    const navigation = { hidden: true, querySelectorAll: () => tabs };
    const tour = { querySelector: () => navigation, querySelectorAll: () => panels };
    runInNewContext(readFileSync(join(__dirname, '../app/static/product-tour.js'), 'utf8'), {
        document: { querySelectorAll: () => [tour] },
    });
    return { tabs, panels, navigation, focus: () => focused };
}

test('selecting a scene exposes only its panel with matching accessible names', () => {
    const ui = setup();
    assert.equal(ui.navigation.hidden, false);
    assert.deepEqual(ui.panels.map(panel => panel.hidden), [false, true, true]);
    ui.tabs[2].events.click();
    assert.deepEqual(ui.panels.map(panel => panel.hidden), [true, true, false]);
    assert.deepEqual(ui.tabs.map(tab => tab.tabIndex), [-1, -1, 0]);
    assert.deepEqual(ui.tabs.map(tab => tab.attributes['aria-selected']), ['false', 'false', 'true']);
    assert.equal(ui.panels[2].attributes['aria-labelledby'], 'tab-2');
    assert.equal(ui.panels[2].attributes.role, 'tabpanel');
});

test('keyboard navigation wraps, supports Home and End, and leaves other keys alone', () => {
    const ui = setup();
    let prevented = 0;
    const press = (index, key) => ui.tabs[index].events.keydown({ key, preventDefault() { prevented++; } });
    press(0, 'ArrowLeft'); assert.equal(ui.focus(), 2);
    press(2, 'ArrowRight'); assert.equal(ui.focus(), 0);
    press(0, 'End'); assert.equal(ui.focus(), 2);
    press(2, 'Home'); assert.equal(ui.focus(), 0);
    press(0, 'Tab'); assert.equal(prevented, 4);
});
