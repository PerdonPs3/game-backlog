const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const { runInNewContext } = require("node:vm");

function setup() {
    const value = { textContent: "3" };
    const badge = { hidden: false, dataset: { memberCountUrl: "/community/member-count" },
        querySelector: () => value, setAttribute(name, text) { this[name] = text; } };
    const doc = { hidden: false, querySelector: () => badge };
    const events = {};
    let tick, reply = { count: 4 }, ok = true, calls = 0, clears = 0;
    runInNewContext(readFileSync(join(__dirname,"../app/static/community-count.js"),"utf8"), {
        document: doc, AbortController,
        window: { setInterval(fn, delay) { assert.equal(delay,60000); tick=fn; return 1; },
            clearInterval() { clears++; }, addEventListener(name, fn) { events[name]=fn; } },
        fetch: async (url) => { calls++; assert.equal(url,"/community/member-count"); return { ok, json: async () => reply }; },
    });
    return { badge, value, doc, events, refresh: () => tick(), get calls() { return calls; }, get clears() { return clears; }, respond(data, success=true) { reply=data; ok=success; } };
}

test("refreshes only the numeric count and pauses while hidden", async () => {
    const ui=setup();
    assert.equal(ui.calls,0);
    await ui.refresh();
    assert.equal(ui.value.textContent,"4");
    assert.equal(ui.badge["aria-label"],"4 activated player accounts");
    ui.doc.hidden=true;
    await ui.refresh();
    assert.equal(ui.calls,1);
});

test("unavailable and invalid responses hide the badge instead of inventing a zero", async () => {
    const ui=setup();
    for (const count of [null,"10",-1,1.5]) {
        ui.respond({count}); await ui.refresh(); assert.equal(ui.badge.hidden,true);
    }
    ui.respond({count:10},false); await ui.refresh(); assert.equal(ui.badge.hidden,true);
    ui.respond({count:0}); await ui.refresh();
    assert.equal(ui.badge.hidden,false); assert.equal(ui.value.textContent,"0");
});

test("leaving stops polling and a restored page resumes it", async () => {
    const ui=setup(); ui.events.pagehide();
    assert.equal(ui.clears,1); await ui.refresh(); assert.equal(ui.calls,0);
    ui.events.pageshow({persisted:true});
    await ui.refresh(); assert.equal(ui.calls,1);
});
