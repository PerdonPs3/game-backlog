const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {join} = require('node:path');
const {runInNewContext} = require('node:vm');

test('help searches answers immediately and restores all topics after clearing the query', () => {
    const handlers = {};
    const input = {value:'', addEventListener:(name,fn)=>handlers[name]=fn};
    const empty = {};
    const library = {dataset:{helpText:'Library add a game platform'},hidden:true};
    const reviews = {dataset:{helpText:'Reviews ratings half stars'},hidden:true};
    const topics = [library,reviews].map(entry=>({hidden:true,querySelectorAll:()=>[entry]}));
    runInNewContext(readFileSync(join(__dirname,'../app/static/help.js'),'utf8'), {
        document:{querySelector:selector=>selector==='[data-help-query]'?input:empty, querySelectorAll:()=>topics},
    });
    assert.ok(topics.every(topic=>!topic.hidden));
    input.value='HALF STARS'; handlers.input();
    assert.equal(topics[0].hidden,true); assert.equal(topics[1].hidden,false);
    assert.equal(empty.hidden,true);
    input.value='zzzz'; handlers.input(); assert.equal(empty.hidden,false);
    input.value=''; handlers.input();
    assert.ok(topics.every(topic=>!topic.hidden)); assert.equal(empty.hidden,true);
});
