const {test} = require('node:test');
const assert = require('node:assert/strict');
const {cropBox, optimizeBackground} = require('../app/static/background-crop.js');

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

test('large decoded backgrounds are resized and optimized before upload without an original file-size restriction', async () => {
    const qualities = [];
    const canvas = {getContext: () => ({fillRect() {}, drawImage() {}}),
        toBlob(resolve, type, quality) {
            assert.equal(type, 'image/jpeg');
            qualities.push(quality);
            resolve({size: quality > .8 ? 3 * 1024 * 1024 : 500000});
        }};
    const result = await optimizeBackground({naturalWidth: 8000, naturalHeight: 4000}, () => canvas);
    assert.equal(result.canvas.width, 2400);
    assert.equal(result.canvas.height, 1200);
    assert.deepEqual(qualities, [.9, .8]);
    assert.equal(result.blob.size, 500000);
});

test('optimization keeps smaller images at their original dimensions and reports encoding failure', async () => {
    const canvas = {getContext: () => ({fillRect() {}, drawImage() {}}), toBlob: resolve => resolve({size: 80000})};
    await optimizeBackground({naturalWidth: 800, naturalHeight: 600}, () => canvas);
    assert.equal(canvas.width, 800);
    assert.equal(canvas.height, 600);
    canvas.toBlob = resolve => resolve(null);
    await assert.rejects(optimizeBackground({naturalWidth: 800, naturalHeight: 600}, () => canvas), /Encoding failed/);
});
