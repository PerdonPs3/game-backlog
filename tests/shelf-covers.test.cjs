const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");

test("shelf images fill their fixed cover frame without distortion or letterboxing", () => {
    const css = readFileSync(join(__dirname, "../app/static/style.css"), "utf8");
    const frame = css.match(/#game-collection\[data-view="shelf"\] \.game-card-cover \{([^}]+)\}/)[1];
    const image = css.match(/#game-collection\[data-view="shelf"\] \.game-card-cover img \{([^}]+)\}/)[1];
    assert.match(frame, /aspect-ratio: 264 \/ 374/);
    for (const declaration of ["position: absolute", "inset: 0", "width: 100%", "height: 100%", "object-fit: cover", "object-position: center"]) {
        assert.ok(image.includes(declaration), declaration);
    }
});
