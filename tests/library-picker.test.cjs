const {test}=require('node:test');
const assert=require('node:assert/strict');
const {readFileSync}=require('node:fs');
const {runInNewContext}=require('node:vm');
class Node {
 constructor(){this.listeners={};this.style={};this.value='';this.innerHTML='Previous result';this.offsetHeight=600;}
 addEventListener(name,fn){this.listeners[name]=fn;}
 fire(name,extra={}){const event={preventDefault(){this.defaultPrevented=true;},...extra};this.listeners[name]?.(event);return event;}
 setAttribute(name,value){this[name]=value;}
 replaceChildren(...options){this.options=options;}
 scrollIntoView(options){this.scroll=options;}
 focus(){this.focused=true;}
}
function setup({spinning=false,reduced=false}={}){
 const form=new Node(),genre=new Node(),outcome=new Node(),feedback=new Node(),submit=new Node(),result=new Node(),document=new Node();
 form.action='/games/pick';form.values=[['pick','1'],['mode','random'],['status','Playing'],['status','Backlog']];form.querySelector=()=>submit;
 const nodes={'.adventure-preferences':form,'#pick-genre':genre,'#pick-outcome':outcome,'#pick-feedback':feedback,'#adventure-result':result};
 document.querySelector=selector=>nodes[selector];document.dispatchEvent=event=>document.fire(event.type);
 let resolve,reject;const requests=[];let starts=0;
 const window={location:{href:'http://localhost/games/pick',origin:'http://localhost'},history:{replaceState(...args){window.url=String(args[2]);}},matchMedia:()=>({matches:reduced}),startAdventureRoulette(){starts++;assert.equal(submit.disabled,false);submit.disabled=spinning;return spinning;}};
 runInNewContext(readFileSync('app/static/library-picker.js','utf8'),{window,document,URL,URLSearchParams,FormData:class{constructor(){return form.values;}},Option:class{constructor(text,value){this.text=text;this.value=value;}},Event:class{constructor(type){this.type=type;}},fetch:(url,options)=>{requests.push({url,options});return new Promise((yes,no)=>{resolve=yes;reject=no;});}});
 return {form,genre,outcome,feedback,submit,result,document,window,requests,starts:()=>starts,resolve:data=>resolve({ok:true,json:async()=>data}),reject:()=>reject(new Error('offline'))};
}
const settle=()=>new Promise(resolve=>setImmediate(resolve));
test('draw updates only outcome, preserves repeated states, and starts roulette enabled',async()=>{
 const ui=setup({spinning:true});
 assert.equal(ui.form.fire('submit').defaultPrevented,true);
 ui.form.fire('submit');assert.equal(ui.requests.length,1);
 assert.deepEqual(ui.requests[0].url.searchParams.getAll('status'),['Playing','Backlog']);
 assert.equal(ui.requests[0].options.headers.Accept,'application/json');
 ui.resolve({html:'New roulette',genres:['Adventure']});await settle();
 assert.equal(ui.outcome.innerHTML,'New roulette');assert.equal(ui.starts(),1);assert.equal(ui.submit.disabled,true);
 assert.equal(ui.outcome.style.minHeight,'600px');assert.equal(ui.feedback.hidden,true);
 ui.document.fire('picker:revealed');assert.equal(ui.outcome.style.minHeight,'');
});
test('direct recommendation scrolls into view respecting reduced motion',async()=>{
 const ui=setup({reduced:true});ui.form.fire('submit');ui.resolve({html:'Recommendation',genres:[]});await settle();
 assert.equal(ui.result.scroll.behavior,'auto');assert.equal(ui.result.focused,true);assert.equal(ui.submit.disabled,false);
});
test('network failures and malformed results keep old result and allow retry',async()=>{
 for(const malformed of [false,true]){
 const ui=setup();ui.form.fire('submit');if(malformed)ui.resolve({html:'bad',genres:[42]});else ui.reject();await settle();
 assert.equal(ui.outcome.innerHTML,'Previous result');assert.equal(ui.submit.disabled,false);assert.match(ui.feedback.textContent,/Please try again/);assert.equal(ui.starts(),0);
 }
});
test('preference edits during request discard stale result',async()=>{
 const ui=setup();ui.form.fire('submit');ui.form.values.push(['genre','Puzzle']);ui.resolve({html:'stale',genres:[]});await settle();
 assert.equal(ui.outcome.innerHTML,'Previous result');assert.match(ui.feedback.textContent,/Preferences changed/);
});
test('plain repeat clicks draw inline while modified clicks keep native navigation',async()=>{
 const ui=setup();const link={href:'http://localhost/games/pick?pick=1',hasAttribute:()=>false};const target={closest:()=>link};
 assert.equal(ui.document.fire('click',{button:0,ctrlKey:true,target}).defaultPrevented,undefined);assert.equal(ui.requests.length,0);
 assert.equal(ui.document.fire('click',{button:0,target}).defaultPrevented,true);ui.resolve({html:'Again',genres:[]});await settle();assert.equal(ui.outcome.innerHTML,'Again');
});
