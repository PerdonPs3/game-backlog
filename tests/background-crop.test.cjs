const {test} = require('node:test');
const assert = require('node:assert/strict');
const {cropBox} = require('../app/static/background-crop.js');

test('banner crops retain their aspect ratio and remain inside portrait and landscape images', () => {
    for (const [width, height] of [[800, 800], [2400, 800], [600, 1800]]) {
        for (const zoom of [1, 2, 4]) {
            for (const [cx, cy] of [[0, 0], [width / 2, height / 2], [width * 2, height * 2]]) {
                const crop = cropBox(width, height, zoom, cx, cy);
                assert.ok(Math.abs(crop.width / crop.height - 8 / 3) < .00001);
                assert.ok(crop.x >= 0 && crop.y >= 0);
                assert.ok(crop.x + crop.width <= width + .00001);
                assert.ok(crop.y + crop.height <= height + .00001);
            }
        }
    }
});
