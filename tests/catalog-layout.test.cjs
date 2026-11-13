const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {runInNewContext} = require('node:vm');
const {join} = require('node:path');

function setup(observerAvailable = true) {
    const events = {}, properties = {}, dataset = {}, observed = [];
    let sidebarHeight = 500, headerHeight = 80, observerCallback;
    const sidebar = {dataset, style:{setProperty:(key,value)=>properties[key]=value}, getBoundingClientRect:()=>({height:sidebarHeight})};
    const header = {getBoundingClientRect:()=>({height:headerHeight})};
    const window = {innerWidth:1440, innerHeight:900, addEventListener:(name,fn)=>events[name]=fn};
    const scope = {window, document:{querySelector:selector=>selector==='.catalog-game-sidebar'?sidebar:header}};
    if (observerAvailable) scope.ResizeObserver=class {constructor(fn){observerCallback=fn;} observe(target){observed.push(target);}};
    runInNewContext(readFileSync(join(__dirname,'../app/static/catalog-layout.js'),'utf8'),scope);
    return {window,events,dataset,properties,observed,setSidebarHeight:value=>sidebarHeight=value,setHeaderHeight:value=>headerHeight=value,resizeObserved:()=>observerCallback()};
}

test('the complete sidebar sticks below the header only when it fits',()=>{
    const view=setup();
    assert.equal(view.dataset.sticky,'true');
    assert.equal(view.properties['--catalog-sidebar-top'],'96px');
    assert.equal(view.observed.length,2);
    view.setSidebarHeight(850); view.resizeObserved();
    assert.equal(view.dataset.sticky,'false');
    view.setSidebarHeight(450); view.setHeaderHeight(120); view.resizeObserved();
    assert.equal(view.dataset.sticky,'true');
    assert.equal(view.properties['--catalog-sidebar-top'],'136px');
});
test('mobile and short viewports retain normal scrolling without hiding controls',()=>{
    const view=setup();
    view.window.innerWidth=390; view.events.resize();
    assert.equal(view.dataset.sticky,'false');
    view.window.innerWidth=1440; view.window.innerHeight=450; view.events.resize();
    assert.equal(view.dataset.sticky,'false');
    view.window.innerHeight=900; view.events.pageshow();
    assert.equal(view.dataset.sticky,'true');
});
test('resize fallback works when ResizeObserver is unavailable',()=>{
    const view=setup(false);
    view.setSidebarHeight(1200); view.events.resize();
    assert.equal(view.dataset.sticky,'false');
});
