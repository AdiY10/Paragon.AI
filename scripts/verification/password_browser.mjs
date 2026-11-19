import {chromium} from '../../frontend/node_modules/@playwright/test/index.mjs';
import assert from 'node:assert/strict';
const base=process.env.PARAGON_QA_BASE,password=process.env.PARAGON_QA_PASSWORD;
if(!base||!password)throw new Error('Use password_smoke.py');
const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined,headless:true});
try{
 const context=await browser.newContext();const page=await context.newPage();
 const errors=[];page.on('pageerror',error=>errors.push(error.message));
 const denied=await context.request.get(base+'/api/locations/');assert.equal(denied.status(),403);
 await page.goto(base);await page.getByRole('heading',{name:'Open your workspace'}).waitFor();
 await page.getByLabel('Email',{exact:true}).fill('access-test@example.invalid');await page.getByLabel('Password',{exact:true}).fill('invalid-test-password');await page.getByRole('button',{name:'Sign in',exact:true}).click();
 await page.getByRole('alert').waitFor();assert.equal((await context.request.get(base+'/api/locations/')).status(),403);
 await page.getByLabel('Password',{exact:true}).fill(password);await page.getByRole('button',{name:'Sign in',exact:true}).click();await page.getByRole('heading',{name:'Your portfolio, in focus.'}).waitFor();await page.getByText('36',{exact:true}).first().waitFor();
 assert.equal((await context.request.get(base+'/api/locations/')).status(),200);
 await page.reload();await page.getByRole('heading',{name:'Your portfolio, in focus.'}).waitFor();
 await page.getByRole('button',{name:'Sign out',exact:true}).click();await page.getByRole('heading',{name:'Open your workspace'}).waitFor();assert.equal((await context.request.get(base+'/api/locations/')).status(),403);assert.deepEqual(errors,[]);
 console.log('Password browser smoke passed: no ChatGPT session, wrong-password denial, real password login, seeded portfolio, persistence, logout, and API denial.');
}finally{await browser.close()}
