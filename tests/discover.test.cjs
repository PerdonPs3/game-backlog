const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {join} = require('node:path');
const {runInNewContext} = require('node:vm');

function setup() {
    const handlers = {}, requests = [], history = [], navigations = [];
    let current;
    function root(id) {
        const status = {textContent: ''}, attrs = {};
        const results = {setAttribute: (key,value) => attrs[key] = value, removeAttribute: key => delete attrs[key]};
        return {id, status, attrs, replaceWith: value => current = value,
            querySelector: selector => selector === '[data-discover-status]' ? status : selector === '.discover-results' ? results : null};
    }
    current = root('original');
    const document = {activeElement: null, addEventListener: (name, fn) => handlers[name] = fn,
        dispatchEvent() {}, querySelector: selector => selector === '[data-discover]' ? current : current.querySelector(selector)};
    class Parser {parseFromString(html) {return {querySelector: () => html === 'invalid' ? null : root(html)};}}
    runInNewContext(readFileSync(join(__dirname,'../app/static/discover.js'),'utf8'), {
        document, DOMParser: Parser, Event: class {}, URL, URLSearchParams, AbortController,
        FormData: class {constructor(form) {return form.values;}},
        history: {pushState: (_, unused, url) => history.push(url)},
        window: {location: {href:'http://localhost/discover', assign: url => navigations.push(url)}, addEventListener: (name,fn) => handlers[name] = fn},
        fetch: (url, options) => new Promise((resolve,reject) => requests.push({url, options, resolve, reject}))
    });
    const form = {action:'http://localhost/discover',values:[['genre','Puzzle'],['platform','6'],['mode','for-you']],requestSubmit:()=>handlers.submit({target:{closest:()=>form},preventDefault(){}})};
    return {handlers,requests,history,navigations, current:()=>current,
        submit() {handlers.submit({target:{closest:()=>form},preventDefault(){}});},
        change(name) {handlers.change({target:{name,closest:()=>form}});},
        click(extra={}) {let prevented=false; handlers.click({button:0,...extra,target:{closest:()=>({href:'http://localhost/discover?page=2'})},preventDefault(){prevented=true;}}); return prevented;},
        resolve(index, html='updated', ok=true) {requests[index].resolve({ok,redirected:false,text:async()=>html});}
    };
}
async function settle() {for (let i=0;i<10;i++) await Promise.resolve();}

test('filters replace the results and URL without navigating away',async()=>{
    const ui=setup();ui.submit();
    assert.match(ui.requests[0].url,/genre=Puzzle&platform=6&mode=for-you/);
    assert.equal(ui.current().attrs['aria-busy'],'true');
    ui.resolve(0);await settle();
    assert.equal(ui.current().id,'updated');assert.equal(ui.history.length,1);
    assert.equal(ui.navigations.length,0);assert.equal(ui.current().status.textContent,'Recommendations updated.');
});
test('out-of-order and edited-filter responses cannot overwrite the latest selection',async()=>{
    const ui=setup();ui.submit();ui.submit();
    assert.equal(ui.requests[0].options.signal.aborted,true);
    ui.resolve(1,'newest');await settle();ui.resolve(0,'stale');await settle();
    assert.equal(ui.current().id,'newest');assert.equal(ui.history.length,1);
    ui.submit();ui.change();ui.resolve(2,'wrong filters');await settle();
    assert.equal(ui.current().id,'newest');assert.equal(ui.requests[2].options.signal.aborted,true);
});
test('failures keep the last successful results and offer retry',async()=>{
    for (const invalid of [false,true]) {
        const ui=setup();ui.submit();ui.resolve(0,invalid?'invalid':'error',invalid);await settle();
        assert.equal(ui.current().id,'original');assert.match(ui.current().status.textContent,/previous results/);
        assert.equal(ui.current().attrs['aria-busy'],undefined);assert.equal(ui.history.length,0);
    }
});
test('changing discovery mode immediately requests updated results',async()=>{
    const ui=setup();ui.change('mode');assert.equal(ui.requests.length,1);
    ui.resolve(0,'popular');await settle();assert.equal(ui.current().id,'popular');
});
test('modified pagination clicks stay native and history navigation does not add entries',async()=>{
    const ui=setup();assert.equal(ui.click({ctrlKey:true}),false);assert.equal(ui.requests.length,0);
    assert.equal(ui.click(),true);ui.resolve(0);await settle();assert.equal(ui.history.length,1);
    ui.handlers.popstate();ui.resolve(1,'back');await settle();
    assert.equal(ui.current().id,'back');assert.equal(ui.history.length,1);
});
