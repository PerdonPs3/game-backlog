const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {join} = require('node:path');
const {runInNewContext} = require('node:vm');

function setup(reduced = false) {
    const handlers = {}, requests = [], scrolls = [], history = [];
    function root(id) {
        const status = {}, attrs = {};
        return {id, status, attrs, setAttribute: (key,value) => attrs[key] = value,
            removeAttribute: key => delete attrs[key], replaceWith: value => current = value,
            querySelector: selector => selector === '[data-catalog-page-status]' ? status
                : selector === '.catalog-results-heading' ? {getBoundingClientRect: () => ({top: 130})} : null};
    }
    let current = root('original');
    runInNewContext(readFileSync(join(__dirname,'../app/static/catalog-pagination.js'),'utf8'), {
        document: {addEventListener: (name, handler) => handlers[name] = handler, dispatchEvent() {},
            querySelector: selector => selector === '[data-catalog-pages]' ? current : {getBoundingClientRect: () => ({bottom:80})}},
        DOMParser: class {parseFromString(html) {return {querySelector: () => html === 'invalid' ? null : root(html)};}},
        Event: class {}, AbortController,
        history: {pushState: (_,unused,url) => history.push(url)},
        window: {scrollY:800, scrollTo: options => scrolls.push(options), matchMedia: () => ({matches:reduced}),
            location: {href:'http://localhost/discover/browse?q=Portal'}, addEventListener: (name, handler) => handlers[name] = handler},
        fetch: (url, options) => new Promise(resolve => requests.push({url, options, resolve})),
    });
    return {requests, scrolls, history, handlers, current: () => current,
        click(direction='next', extra={}) {let prevented = false; handlers.click({button:0,...extra,
            target: {closest: () => ({href:'http://localhost/discover/browse?q=Portal&page=2', dataset:{catalogPage:direction}})},
            preventDefault() {prevented = true;}}); return prevented;},
        resolve(index, html='updated', ok=true) {requests[index].resolve({ok,redirected:false,text:async()=>html});}};
}
async function settle() {for (let index=0;index<12;index++) await Promise.resolve();}

test('search Next aligns the results header while Previous preserves the scroll position', async () => {
    for (const direction of ['next','previous']) {
        for (const reduced of [false,true]) {
            const ui=setup(reduced); ui.click(direction);
            assert.equal(ui.scrolls.length,0);
            ui.resolve(0); await settle();
            assert.equal(ui.current().id,'updated');
            assert.equal(ui.scrolls[0].top,direction==='next'?842:800);
            assert.equal(ui.scrolls[0].behavior,direction==='next'&&!reduced?'smooth':'instant');
            assert.equal(ui.history.length,1);
        }
    }
});

test('failed or stale search pages never move the viewport or replace the latest games', async () => {
    const failed=setup(); failed.click(); failed.resolve(0,'error',false); await settle();
    assert.equal(failed.current().id,'original');
    assert.equal(failed.scrolls.length,0);
    assert.match(failed.current().status.textContent,/Please try again/);
    const ui=setup(); ui.click(); ui.click('previous');
    assert.equal(ui.requests[0].options.signal.aborted,true);
    ui.resolve(1,'newest'); await settle(); ui.resolve(0,'stale'); await settle();
    assert.equal(ui.current().id,'newest');
    assert.equal(ui.scrolls.length,1);
    assert.equal(ui.scrolls[0].top,800);
});

test('modified search links stay native and browser history does not push another entry', async () => {
    const ui=setup(); assert.equal(ui.click('next',{ctrlKey:true}),false);
    assert.equal(ui.requests.length,0);
    ui.handlers.popstate(); ui.resolve(0,'back'); await settle();
    assert.equal(ui.current().id,'back');
    assert.equal(ui.history.length,0);
});
