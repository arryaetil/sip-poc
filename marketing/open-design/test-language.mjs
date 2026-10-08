import assert from 'node:assert/strict';
import {chromium} from 'playwright-core';
import {STUDIO_LANGUAGE_SCRIPT} from './studio-language.mjs';
const browser=await chromium.launch({executablePath:process.env.STUDIO_CHROMIUM_PATH,headless:true});
try{
const page=await browser.newPage();
const script=STUDIO_LANGUAGE_SCRIPT.replace("'SIP_STUDIO_LANGUAGE'",JSON.stringify('nl')).replace("'SIP_LANGUAGE_PARENT_ORIGIN'",JSON.stringify('http://parent.invalid'));
await page.route('http://parent.invalid/**',route=>route.fulfill({contentType:'text/html; charset=utf-8',body:'<button onclick="document.querySelector(\'iframe\').contentWindow.postMessage({type:\'sip-studio-language\',language:this.textContent},\'http://studio.invalid\')">en</button><button onclick="document.querySelector(\'iframe\').contentWindow.postMessage({type:\'sip-studio-language\',language:this.textContent},\'http://studio.invalid\')">de</button><button onclick="document.querySelector(\'iframe\').contentWindow.postMessage({type:\'sip-studio-language\',language:this.textContent},\'http://studio.invalid\')">nl</button><iframe src="http://studio.invalid/"></iframe><iframe src="http://rogue.invalid/"></iframe>'}));
await page.route('http://studio.invalid/**',route=>route.fulfill({contentType:'text/html; charset=utf-8',body:'<html><head>'+script+'</head><body><div class="home-hero"><h1 class="home-hero__title">Let’s create</h1><p class="home-hero__subtitle">Good work starts here</p><div role="combobox" contenteditable="true">Home</div><button>Run</button></div><nav class="entry-nav-rail"><button>All projects</button><button class="entry-nav-rail__recent-item">Home</button></nav><div id="app-chrome-file-actions"><button>Export</button></div><article data-user-artwork>Home — mijn eigen ontwerp</article></body></html>'}));
await page.route('http://rogue.invalid/**',route=>route.fulfill({contentType:'text/html; charset=utf-8',body:'<button onclick="parent.frames[0].postMessage({type:\'sip-studio-language\',language:\'en\'},\'http://studio.invalid\')">Rogue</button>'}));
await page.goto('http://parent.invalid/');
await page.frameLocator('iframe[src="http://studio.invalid/"]').getByRole('button',{name:'Maken'}).waitFor({state:'visible'});
const frame=page.frameLocator('iframe[src="http://studio.invalid/"]');
assert.equal(await frame.getByRole('combobox').textContent(),'Home');
assert.equal(await frame.locator('.entry-nav-rail__recent-item').textContent(),'Home');
await page.getByRole('button',{name:'en',exact:true}).click();await frame.getByRole('button',{name:'Run'}).waitFor({state:'visible'});
assert.equal(await frame.locator('.home-hero__title').getAttribute('aria-label'),'What would you like to create?');
await page.getByRole('button',{name:'de',exact:true}).click();await frame.getByRole('button',{name:'Erstellen'}).waitFor({state:'visible'});
assert.equal(await frame.locator('.home-hero__title').getAttribute('aria-label'),'Was möchtest du erstellen?');
await page.frameLocator('iframe[src="http://rogue.invalid/"]').getByRole('button',{name:'Rogue'}).click();
assert.equal(await frame.locator('.home-hero__title').getAttribute('aria-label'),'Was möchtest du erstellen?');
await page.getByRole('button',{name:'nl',exact:true}).click();await frame.getByRole('button',{name:'Maken'}).waitFor({state:'visible'});
assert.equal(await frame.locator('.home-hero__title').getAttribute('aria-label'),'Wat wil je maken?');
assert.equal(await frame.getByRole('combobox').textContent(),'Home');
assert.equal(await frame.locator('[data-user-artwork]').textContent(),'Home — mijn eigen ontwerp');
console.log('NL/EN/DE live language changes preserve drafts, project names and artwork; foreign-frame messages are rejected');
}finally{await browser.close();}
