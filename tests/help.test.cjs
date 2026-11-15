const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {join} = require('node:path');
const {runInNewContext} = require('node:vm');

test('help searches answers immediately and restores all topics after clearing the query', () => {
    const handlers = {};
    const input = {value:'', addEventListener:(name,fn)=>handlers[name]=fn};
    const empty = {};
    const library = {dataset:{helpText:'Library add a game platform'},hidden:true,querySelector:()=>null};
    const reviews = {dataset:{helpText:'Reviews ratings half stars'},hidden:true,querySelector:()=>null};
    const topics = [library,reviews].map(entry=>({hidden:true,querySelectorAll:()=>[entry]}));
    runInNewContext(readFileSync(join(__dirname,'../app/static/help.js'),'utf8'), {
        document:{querySelector:selector=>selector==='[data-help-query]'?input:empty, querySelectorAll:selector=>selector==='[data-help-topic]'?topics:[],addEventListener:()=>{}},
    });
    assert.ok(topics.every(topic=>!topic.hidden));
    input.value='HALF STARS'; handlers.input();
    assert.equal(topics[0].hidden,true); assert.equal(topics[1].hidden,false);
    assert.equal(empty.hidden,true);
    input.value='zzzz'; handlers.input(); assert.equal(empty.hidden,false);
    input.value=''; handlers.input();
    assert.ok(topics.every(topic=>!topic.hidden)); assert.equal(empty.hidden,true);
});

function demoPage(reducedMotion = false) {
    const events = {}, documentEvents = {}, inputEvents = {};
    const replay = {hidden:true, addEventListener:(name,fn)=>events.replay=fn};
    const entry = {open:false, hidden:false, dataset:{helpText:'Library add a game'},
        querySelector:selector=>selector==='[data-help-video]'?video:replay,
        addEventListener:(name,fn)=>events.toggle=fn};
    const video = {dataset:{src:'/static/videos/help-add-game.mp4'},paused:true,currentTime:0,loads:0,plays:0,
        closest:()=>entry,getAttribute:()=>video.src,
        load:()=>video.loads++,play:()=>{video.paused=false;video.plays++;return Promise.resolve();},pause:()=>video.paused=true};
    const input = {value:'',addEventListener:(name,fn)=>inputEvents[name]=fn};
    const topic = {querySelectorAll:()=>[entry]};
    const document = {hidden:false,querySelector:selector=>selector==='[data-help-query]'?input:{},
        querySelectorAll:selector=>selector==='[data-help-topic]'?[topic]:[video],
        addEventListener:(name,fn)=>documentEvents[name]=fn};
    runInNewContext(readFileSync(join(__dirname,'../app/static/help.js'),'utf8'), {
        document,window:{matchMedia:()=>({matches:reducedMotion})},
    });
    return {events,documentEvents,inputEvents,entry,video,input,document,replay};
}

test('demo loads on opening, pauses on closing, and can replay without reloading', () => {
    const page = demoPage();
    assert.equal(page.video.loads,0);
    assert.equal(page.replay.hidden,false);
    page.entry.open=true; page.events.toggle();
    assert.equal(page.video.loads,1); assert.equal(page.video.paused,false);
    page.entry.open=false; page.events.toggle();
    assert.equal(page.video.paused,true);
    page.video.currentTime=15; page.events.replay();
    assert.equal(page.video.currentTime,0); assert.equal(page.video.loads,1);
});

test('reduced motion keeps manual playback and hidden content pauses the clip', () => {
    const page = demoPage(true);
    page.entry.open=true; page.events.toggle();
    assert.equal(page.video.loads,1); assert.equal(page.video.plays,0);
    page.events.replay(); assert.equal(page.video.plays,1);
    page.input.value='ratings'; page.inputEvents.input();
    assert.equal(page.entry.hidden,true); assert.equal(page.video.paused,true);
    page.events.replay(); page.document.hidden=true; page.documentEvents.visibilitychange();
    assert.equal(page.video.paused,true);
});
