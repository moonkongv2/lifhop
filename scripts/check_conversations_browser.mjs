// Standalone headless verification; does not control the Codex in-app browser.
import assert from 'node:assert/strict';
import { mkdir, writeFile, chmod } from 'node:fs/promises';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
const { chromium } = await import(pathToFileURL(resolve('.local/verification/browser-tools/node_modules/playwright/index.mjs')));
const root=resolve('.local/verification/conversations-browser');
await mkdir(root,{recursive:true,mode:0o700});
const origin=process.env.LIFHOP_DEMO_ORIGIN??'http://127.0.0.1:5175';
assert.match(origin,/^http:\/\/(127\.0\.0\.1|localhost):\d+$/);
const browser=await chromium.launch({headless:true,executablePath:process.env.LIFHOP_CHROMIUM_PATH??'/Users/moonkong/Library/Caches/ms-playwright/chromium_headless_shell-1234/chrome-headless-shell-mac-arm64/chrome-headless-shell'});
const context=await browser.newContext({viewport:{width:1280,height:1000}});
const page=await context.newPage();page.setDefaultTimeout(10000);
const errors=[],checks=[],blocked=[];
page.on('pageerror',e=>errors.push(e.message));
await context.route('**/*',route=>{
  const url=new URL(route.request().url());
  if(!['127.0.0.1','localhost'].includes(url.hostname)){blocked.push(url.origin);return route.abort();}
  return route.continue();
});
const stats=async()=>{const r=await page.request.get(origin+'/api/__demo/status?check='+Date.now());assert.equal(r.status(),200);const v=await r.json();assert.equal(v.synthetic,true);return v;};
const snap=async(name)=>{const p=root+'/'+name+'.png';await page.screenshot({path:p,fullPage:true});await chmod(p,0o600);};
const login=async(email='demo@example.test')=>{
 await page.getByLabel('Email',{exact:true}).fill(email);
 await page.getByLabel('Password',{exact:true}).fill('demo-password');
 await page.getByRole('button',{name:'Log in',exact:true}).click();
 await page.getByRole('button',{name:'Logout',exact:true}).waitFor();
};
const send=async(q)=>{
 await page.getByRole('textbox',{name:'Question',exact:true}).fill(q);
 await page.getByRole('checkbox',{name:'Allow this question and its context to be sent to OpenAI',exact:true}).check();
 await page.getByRole('button',{name:'Send question',exact:true}).click();
};
const completed=async(n)=>{
 await page.getByRole('heading',{name:`Question ${n}`,exact:true}).waitFor();
 await page.waitForFunction(n=>document.querySelectorAll('.saved-conversation article .entry-content').length>=n*2,n);
};
try{
 await page.goto(origin+'/login');await login();
 await page.getByRole('link',{name:'Search',exact:true}).click();
 await page.getByLabel('Search query',{exact:true}).fill('worker');
 await page.getByRole('button',{name:'Search',exact:true}).click();
 await page.getByRole('button',{name:'Get an answer with sources',exact:true}).click();
 await page.getByRole('checkbox',{name:'Allow this question and selected originals to be sent to OpenAI and save this conversation',exact:true}).check();
 await page.getByRole('button',{name:'Ask from my records',exact:true}).click();
 await page.waitForURL(/\/conversations\/[a-f0-9]{32}$/);await completed(1);
 const url=page.url(),cid=url.split('/').at(-1);
 assert.deepEqual((await stats()).calls,{plan:0,query:1,answer:1});checks.push('first question persisted');
 await page.getByRole('link',{name:/Original · Version/}).first().click();
 await page.getByText('This citation matches the current retained version.',{exact:true}).waitFor();
 await page.getByRole('link',{name:'Back to conversation',exact:true}).click();await completed(1);
 assert.deepEqual((await stats()).calls,{plan:0,query:1,answer:1});checks.push('stable citation return has zero provider calls');
 await send('Explain that again.');await completed(2);
 assert.deepEqual((await stats()).calls,{plan:1,query:1,answer:2});checks.push('reuse follow-up');
 await send('ambiguous subject');
 await page.getByText('Which synthetic company do you mean?',{exact:true}).waitFor();
 assert.deepEqual((await stats()).calls,{plan:2,query:1,answer:2});checks.push('clarify has no query/answer');
 await send('The first company.');await completed(4);
 await send('Find later cancellation.');await completed(5);
 assert.deepEqual((await stats()).calls,{plan:4,query:2,answer:4});checks.push('clarification reply and search follow-up');
 await snap('desktop');
 const before=(await stats()).calls;
 await page.getByRole('button',{name:'Close conversation',exact:true}).click();
 await page.getByRole('button',{name:'Reopen conversation',exact:true}).waitFor();
 await page.getByRole('button',{name:'Logout',exact:true}).click();await login();
 await page.getByRole('link',{name:'Conversations',exact:true}).click();
 await page.getByRole('link',{name:'worker',exact:true}).click();await completed(5);
 assert.deepEqual((await stats()).calls,before);
 await page.getByRole('button',{name:'Reopen conversation',exact:true}).click();
 await page.getByRole('button',{name:'Close conversation',exact:true}).waitFor();checks.push('close/logout/login/list/reopen without provider calls');
 await page.setViewportSize({width:390,height:844});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
 await snap('mobile');checks.push('mobile no horizontal overflow');
 await send('slow explanation');
 // Observe the test-only transport counter rather than waiting for the long response.
 const deadline=Date.now()+10000;
 while((await stats()).calls.answer!==5 && Date.now()<deadline) await new Promise(r=>setTimeout(r,100));
 assert.equal((await stats()).calls.answer,5,'answer transport must be running before Stop');
 await page.getByRole('button',{name:'Stop unfinished question',exact:true}).click();
 await page.getByText('stopped',{exact:true}).waitFor();
 await page.request.post(origin+'/api/__demo/release');
 await page.getByRole('button',{name:'Refresh saved state',exact:true}).click();
 await page.getByRole('heading',{name:'Question 6',exact:true}).waitFor();checks.push('stop during provider');
 await page.getByRole('button',{name:'Logout',exact:true}).click();await login('other@example.test');
 await page.goto(url);
 await page.getByRole('alert').filter({hasText:'Conversation unavailable'}).waitFor();
 assert.equal(await page.getByText('worker',{exact:true}).count(),0);checks.push('other account cannot view conversation');
 await page.getByRole('button',{name:'Logout',exact:true}).click();await login();await page.goto(url);await completed(5);
 await send('slow delete explanation');
 const deleteDeadline=Date.now()+10000;
 while((await stats()).calls.answer!==6 && Date.now()<deleteDeadline) await new Promise(r=>setTimeout(r,100));
 assert.equal((await stats()).calls.answer,6);
 await page.getByRole('button',{name:'Delete conversation',exact:true}).click();
 await page.request.post(origin+'/api/__demo/release');
 await page.waitForURL(/\/conversations$/);await page.getByText('No saved conversations yet.',{exact:true}).waitFor();
 await page.goto(origin+'/conversations/'+cid);
 await page.getByRole('alert').filter({hasText:'Conversation unavailable'}).waitFor();checks.push('delete prevents restoration');
 assert.deepEqual(errors,[]);assert.deepEqual(blocked,[]);
 let final=await stats();
 const settleDeadline=Date.now()+10000;
 while(final.usage.spent!==14 && Date.now()<settleDeadline){await new Promise(r=>setTimeout(r,100));final=await stats();}
 assert.deepEqual(final.calls,{plan:6,query:2,answer:6});assert.deepEqual(final.usage,{spent:14});
 const report={passed:true,checks,stats:final,browserErrors:errors,blockedExternalOrigins:blocked};
 await writeFile(root+'/report.json',JSON.stringify(report,null,2),{mode:0o600});console.log(JSON.stringify(report));
}catch(e){await snap('failure');await writeFile(root+'/failure.txt',String(e),{mode:0o600});throw e;}
finally{await browser.close();}
