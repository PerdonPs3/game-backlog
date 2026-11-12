const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const { runInNewContext } = require("node:vm");
function setup(reduced=false){
    const events={},timers=[],destinations=[],classes=new Set();
    const win={location:{origin:"http://localhost",assign:url=>destinations.push(url)},
        matchMedia:()=>({matches:reduced}),setTimeout:f=>{timers.push(f);return 1;},clearTimeout(){},addEventListener:(n,f)=>events[n]=f};
    runInNewContext(readFileSync(join(__dirname,"../app/static/catalog-navigation.js"),"utf8"),{
        URL,window:win,document:{body:{classList:{add:c=>classes.add(c),remove:c=>classes.delete(c)}},addEventListener:(n,f)=>events[n]=f},
    });
    return {events,timers,destinations,classes,go:win.VestigiumCatalogNavigation.go,
        click(extra={}){let prevented=false;events.click({button:0,target:{closest:()=>({href:"http://localhost/explore/games/72",target:"",hasAttribute:()=>false})},preventDefault(){prevented=true;},...extra});return prevented;}};
}
test("ordinary game selection fades once before opening its public page",()=>{
    const ui=setup();assert.equal(ui.click(),true);ui.click();
    assert.equal(ui.timers.length,1);assert.ok(ui.classes.has("is-opening-game"));
    assert.equal(ui.destinations.length,0);ui.timers[0]();assert.equal(ui.destinations[0],"http://localhost/explore/games/72");
    ui.events.pageshow();assert.equal(ui.classes.size,0);
});
test("modified clicks and unrelated or external destinations keep native navigation",()=>{
    for(const extra of [{ctrlKey:true},{metaKey:true},{shiftKey:true},{altKey:true},{button:1},{defaultPrevented:true}]){
        const ui=setup();assert.equal(ui.click(extra),false);assert.equal(ui.timers.length,0);
    }
    const ui=setup();assert.equal(ui.go("https://other.example/explore/games/72"),false);
    assert.equal(ui.go("/games/72"),false);assert.equal(ui.go("/explore/games/72/add"),false);
});
test("reduced motion opens directly without a fade or delay",()=>{
    const ui=setup(true);assert.equal(ui.click(),true);assert.equal(ui.classes.size,0);
    assert.equal(ui.timers.length,0);assert.equal(ui.destinations.length,1);
});

// Public catalog IDs must never be confused with private entry IDs.
test("canonical game links retain return filters and the private progress anchor",()=>{
    const ui=setup();
    const target="/games/72/portal-2?from=%2Flibrary%3Fstatus%3DPlaying#your-progress";
    assert.equal(ui.go(target),true);ui.timers[0]();
    assert.equal(ui.destinations[0],"http://localhost"+target);
});
test("private entries and write actions keep ordinary browser navigation",()=>{
    const ui=setup();
    for(const path of ["/library/entries/72", "/library/entries/72/edit", "/games/72", "/games/72/portal-2/edit"]){
        assert.equal(ui.go(path),false);
    }
    assert.equal(ui.timers.length,0);
});
