const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { runInNewContext } = require('node:vm');

function setup() {
    const previews = [];
    const node = () => ({ dataset: {}, events: {}, attrs: {}, hidden: false,
        addEventListener(name, handler) { this.events[name] = handler; },
        setAttribute(name, value) { this.attrs[name] = value; },
        removeAttribute(name) { delete this.attrs[name]; } });
    const video = node(), image = node();
    video.dataset = { kind: 'video', mediaId: 'KOiuc9UWz1E', preview: 'https://i.ytimg.com/vi/KOiuc9UWz1E/hqdefault.jpg', title: 'Trailer' };
    video.href = 'https://www.youtube.com/watch?v=KOiuc9UWz1E';
    image.dataset = { kind: 'image', title: 'Screenshot 1' };
    image.href = 'https://images.igdb.com/igdb/image/upload/t_screenshot_huge/shot.jpg';
    let frame;
    const stage = { dataset: {}, querySelector: () => frame, append(value) { frame = value; } };
    const nodes = Object.fromEntries(['poster', 'play', 'caption', 'position', 'external'].map(key => [`[data-media-${key}]`, node()]));
    nodes['[data-media-stage]'] = stage;
    const gallery = { querySelectorAll: () => [video, image], querySelector: key => nodes[key] };
    runInNewContext(readFileSync('app/static/catalog-media.js', 'utf8'), {
        Image: class { constructor() { previews.push(this); } },
        document: { querySelectorAll: () => [gallery], createElement: () => ({ focus() {}, remove() { frame = undefined; } }) },
    });
    return { video, image, nodes, previews, get frame() { return frame; } };
}

test('a gallery loads no player before play and switching stops the current video', () => {
    const ui = setup();
    assert.equal(ui.frame, undefined);
    assert.equal(ui.nodes['[data-media-play]'].hidden, false);
    ui.nodes['[data-media-play]'].events.click();
    assert.match(ui.frame.src, /^https:\/\/www.youtube-nocookie.com\/embed\/KOiuc9UWz1E\?/);
    assert.equal(ui.frame.referrerPolicy, 'strict-origin-when-cross-origin');
    let prevented = false;
    ui.image.events.click({ preventDefault() { prevented = true; } });
    assert.equal(prevented, true);
    assert.equal(ui.frame, undefined);
    assert.equal(ui.nodes['[data-media-play]'].hidden, true);
    assert.equal(ui.nodes['[data-media-poster]'].src, ui.image.href);
    assert.equal(ui.image.attrs['aria-current'], 'true');
});

test('modified clicks keep the external link and malformed video IDs never create frames', () => {
    const ui = setup();
    ui.image.events.click({ ctrlKey: true, preventDefault() { assert.fail('Keep modified clicks native'); } });
    ui.video.dataset.mediaId = '../injected';
    ui.nodes['[data-media-play]'].events.click();
    assert.equal(ui.frame, undefined);
});

test('large video previews use maximum resolution and cache a successful image', () => {
    const ui = setup();
    const preview = ui.previews[0];
    assert.match(preview.src, /\/maxresdefault\.jpg$/);
    preview.naturalWidth = 1280;
    preview.onload();
    assert.equal(ui.nodes['[data-media-poster]'].src, preview.src);
    ui.video.events.click({ preventDefault() {} });
    assert.equal(ui.previews.length, 1);
});

test('missing or placeholder high-resolution images fall back without breaking the poster', () => {
    const ui = setup();
    ui.previews[0].naturalWidth = 120;
    ui.previews[0].onload();
    assert.match(ui.previews[1].src, /\/sddefault\.jpg$/);
    ui.previews[1].onerror();
    assert.equal(ui.nodes['[data-media-poster]'].src, ui.video.dataset.preview);
});

test('a slow video preview cannot replace a newly selected screenshot', () => {
    const ui = setup();
    ui.image.events.click({ preventDefault() {} });
    ui.previews[0].naturalWidth = 1280;
    ui.previews[0].onload();
    assert.equal(ui.nodes['[data-media-poster]'].src, ui.image.href);
});
