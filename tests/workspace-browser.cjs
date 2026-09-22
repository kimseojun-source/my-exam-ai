const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true});const page=await browser.newPage({viewport:{width:1366,height:900}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/api/**',r=>r.fulfill({contentType:'application/json',body:JSON.stringify(r.request().url().endsWith('/profiles')?[]:{})}));
 await page.goto('http://localhost:8765/');await page.waitForTimeout(500);
 await page.evaluate(()=>{document.querySelector('#app').classList.remove('hidden');document.querySelector('#gate').classList.add('hidden');document.querySelector('#ws').classList.remove('hidden');});
 assert.equal(await page.locator('.study-source').isVisible(),true);assert.equal(await page.locator('.study-explanation').isVisible(),true);
 await page.getByRole('button',{name:'과목과 자료 메뉴',exact:true}).click();assert.equal(await page.locator('#files').isVisible(),true);assert.equal(await page.locator('#courses').isVisible(),true);
 await page.getByRole('button',{name:'메뉴 닫기',exact:true}).click();assert.equal(await page.locator('#files').isVisible(),false);
 await page.setViewportSize({width:390,height:844});assert.equal(await page.locator('.study-source').isVisible(),false);
 await page.locator('[data-view="source"]').click();assert.equal(await page.locator('.study-source').isVisible(),true);assert.equal(await page.locator('.study-explanation').isVisible(),false);
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
 assert.deepEqual(errors,[]);await browser.close();console.log('Workspace: tablet split, drawer, mobile tabs, overflow, JS errors passed');
})();
