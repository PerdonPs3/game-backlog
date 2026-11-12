const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const { runInNewContext } = require('node:vm');
function setup(href, enabled=true) {
    const links=['/library','/library/wishlist','/library/lists','/library/pick'].map(path=>({href:'http://localhost'+path}));
    const events={};
    const window={location:{href}};
    runInNewContext(readFileSync(join(__dirname,'../app/static/library-sections.js'),'utf8'),{
        URL,window,document:{
            querySelector:selector=>!enabled?null:selector==='#collection-filters'?{}:{querySelectorAll:()=>links},
            addEventListener:(name,fn)=>events[name]=fn,
        },
    });
    return {links,events,window};
}
test('live collection filters follow the user into each sibling tab',()=>{
    const ui=setup('http://localhost/library?q=Portal&status=Playing&sort=rating');
    ui.events['collection:updated']();
    assert.equal(ui.links[0].href,ui.window.location.href);
    for(const link of ui.links.slice(1)){
        assert.equal(new URL(link.href).searchParams.get('from'),'/library?q=Portal&status=Playing&sort=rating');
    }
});
test('clearing filters removes stale context and leaves unrelated pages alone',()=>{
    const ui=setup('http://localhost/library?q=Portal');
    ui.events['collection:updated']();
    ui.window.location.href='http://localhost/library';
    ui.events['collection:updated']();
    assert.equal(new URL(ui.links[1].href).searchParams.has('from'),false);
    assert.equal(Object.keys(setup('http://localhost/discover',false).events).length,0);
});
