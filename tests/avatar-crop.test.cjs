const { test } = require('node:test');
const assert = require('node:assert/strict');
const { constrain, move } = require('../app/static/avatar-crop.js');

test('portrait and landscape crops start centered and stay square at any zoom', () => {
    for (const [width, height] of [[1200, 800], [800, 1200], [100, 100]]) {
        const state = { width, height, cx: width / 2, cy: height / 2, zoom: 1 };
        assert.deepEqual(constrain(state), { x: (width - Math.min(width, height)) / 2, y: (height - Math.min(width, height)) / 2, size: Math.min(width, height) });
        state.zoom = 4;
        assert.equal(constrain(state).size, Math.min(width, height) / 4);
    }
});

test('dragging moves the photo in the pointer direction without exposing empty crop pixels', () => {
    const state = { width: 1200, height: 800, cx: 600, cy: 400, zoom: 2 };
    move(state, 64, 0);
    assert.equal(state.cx, 500);
    for (const [dx, dy] of [[10000, 10000], [-10000, -10000]]) {
        const box = move(state, dx, dy);
        assert.ok(box.x >= 0 && box.y >= 0);
        assert.ok(box.x + box.size <= state.width && box.y + box.size <= state.height);
    }
    state.zoom = 1;
    const box = constrain(state);
    assert.equal(box.y, 0);
    assert.ok(box.x >= 0 && box.x <= 400);
});
