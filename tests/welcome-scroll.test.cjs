const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const { runInNewContext } = require("node:vm");
function setup(reduced=false) {
    const events={}, calls=[], timers=[];
    const hero={bottom:800,getBoundingClientRect(){return {bottom:this.bottom};},scrollIntoView(options){calls.push({...options,cover:true});}};
    const story={scrollIntoView(options){calls.push(options);}};
    const target={closest:()=>null};
    runInNewContext(readFileSync(join(__dirname,"../app/static/welcome-scroll.js"),"utf8"),{
        document:{querySelector:s=>s===".welcome-hero"?hero:story,addEventListener:(n,f)=>events[n]=f},
        window:{innerHeight:800,matchMedia:()=>({matches:reduced}),addEventListener:(n,f)=>events[n]=f,
            setTimeout:f=>{timers.push(f);return 1;},clearTimeout(){}},
    });
    return {events,calls,timers,hero,target,wheel(extra={}){let prevented=false;events.wheel({deltaY:30,deltaMode:0,target,preventDefault(){prevented=true;},...extra});return prevented;}};
}

test("downward intent advances once from the cover and does not hijack the story",()=>{
    const ui=setup();assert.equal(ui.wheel(),true);assert.equal(ui.calls.length,1);
    assert.equal(ui.calls[0].behavior,"smooth");ui.wheel();assert.equal(ui.calls.length,1);
    ui.timers[0]();ui.hero.bottom=0;assert.equal(ui.wheel(),false);assert.equal(ui.calls.length,1);
});
test("typing, scrolling suggestions, zoom gestures and reduced motion retain native behavior",()=>{
    for (const extra of [{target:{closest:()=>({})}},{ctrlKey:true},{deltaY:-40}]) {
        const ui=setup();assert.equal(ui.wheel(extra),false);assert.equal(ui.calls.length,0);
    }
    const ui=setup(true);assert.equal(ui.wheel(),false);assert.equal(ui.calls.length,0);
});
test("PageDown and a vertical touch swipe can advance, while horizontal swipes cannot",()=>{
    const ui=setup();let prevented=false;
    ui.events.keydown({key:"PageDown",target:ui.target,preventDefault(){prevented=true;}});
    assert.equal(prevented,true);assert.equal(ui.calls.length,1);
    const touch=setup();touch.events.touchstart({target:touch.target,touches:[{clientX:0,clientY:400}]});
    touch.events.touchend({changedTouches:[{clientX:150,clientY:350}]});assert.equal(touch.calls.length,0);
    touch.events.touchstart({target:touch.target,touches:[{clientX:0,clientY:400}]});
    touch.events.touchend({changedTouches:[{clientX:0,clientY:200}]});assert.equal(touch.calls.length,1);
});

test("upward intent returns to the cover only near the story boundary",()=>{
    const ui=setup();ui.hero.bottom=-500;
    assert.equal(ui.wheel({deltaY:-60}),false);assert.equal(ui.calls.length,0);
    ui.hero.bottom=0;assert.equal(ui.wheel({deltaY:-60}),true);
    assert.equal(ui.calls.length,1);assert.equal(ui.calls[0].cover,true);
    assert.equal(ui.calls[0].behavior,"smooth");
    ui.wheel({deltaY:-60});ui.wheel({deltaY:60});assert.equal(ui.calls.length,1);
    ui.timers[0]();ui.hero.bottom=800;
    assert.equal(ui.wheel({deltaY:-60}),false);assert.equal(ui.calls.length,1);
    assert.equal(ui.wheel(),true);assert.equal(ui.calls.length,2);
});

test("PageUp, Shift+Space and downward touch swipes can return without hijacking deeper content",()=>{
    for (const key of [{key:"PageUp"},{key:" ",shiftKey:true}]) {
        const ui=setup();ui.hero.bottom=0;let prevented=false;
        ui.events.keydown({...key,target:ui.target,preventDefault(){prevented=true;}});
        assert.equal(prevented,true);assert.equal(ui.calls[0].cover,true);
    }
    const ui=setup();ui.hero.bottom=-500;
    ui.events.touchstart({target:ui.target,touches:[{clientX:0,clientY:100}]});
    ui.events.touchend({changedTouches:[{clientX:0,clientY:250}]});assert.equal(ui.calls.length,0);
    ui.hero.bottom=0;
    ui.events.touchstart({target:ui.target,touches:[{clientX:0,clientY:100}]});
    ui.events.touchend({changedTouches:[{clientX:0,clientY:250}]});assert.equal(ui.calls[0].cover,true);
    const reduced=setup(true);reduced.hero.bottom=0;
    assert.equal(reduced.wheel({deltaY:-60}),false);assert.equal(reduced.calls.length,0);
});
