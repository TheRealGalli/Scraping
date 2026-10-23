import { chromium } from '/Users/carlogalli/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs';
import fs from 'node:fs/promises';
import path from 'node:path';

const root = path.resolve(import.meta.dirname, '..');
const output = path.join(root, 'templates/campaigns/screenshots');
await fs.mkdir(output, { recursive: true });
const browser = await chromium.launch({ headless: true, channel: 'chrome' });
const page = await browser.newPage({ viewport: { width: 760, height: 1000 }, deviceScaleFactor: 1 });
const ids = ['consulenza', 'training', 'nfc', 'sito', 'social', 'media'];
const errors = [];
page.on('pageerror', error => errors.push(error.message));
page.on('response', response => { if (response.status() >= 400) errors.push(`${response.status()} ${response.url()}`); });
for (const id of ids) {
  await page.setViewportSize({ width: 760, height: 1000 });
  await page.goto(`http://127.0.0.1:8765/templates/campaigns/${id}.html`);
  await page.locator('img').evaluateAll(images => Promise.all(images.map(img => img.decode())));
  const desktop = await page.evaluate(() => ({ overflow: document.documentElement.scrollWidth > innerWidth, images: [...document.images].every(i => i.complete && i.naturalWidth > 0), bytes: new TextEncoder().encode(document.documentElement.outerHTML).length }));
  if (desktop.overflow || !desktop.images) errors.push(`${id} desktop layout/image check failed`);
  await page.screenshot({ path: path.join(output, `${id}.png`), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: path.join(output, `${id}-mobile.png`), fullPage: true });
  const mobileOverflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
  if (mobileOverflow) errors.push(`${id} mobile overflow`);
  console.log(JSON.stringify({ id, ...desktop, mobileOverflow }));
}
await page.setViewportSize({ width: 1440, height: 1050 });
await page.goto('http://127.0.0.1:8765/templates/campaigns/index.html');
await page.frameLocator('iframe').locator('img').evaluateAll(images => Promise.all(images.map(img => img.decode())));
for (const id of ids) {
  await page.locator(`[data-id="${id}"]`).click();
  await page.waitForFunction(id => document.getElementById('email').contentDocument?.title.includes(({consulenza:'Consulenza AI',training:'Training AI',nfc:'Card NFC',sito:'Sito web',social:'Social',media:'Slide e video'})[id]), id);
}
await page.locator('[data-id="consulenza"]').click();
await page.frameLocator('iframe').locator('img').evaluateAll(images => Promise.all(images.map(img => img.decode())));
await page.screenshot({ path: path.join(output, 'galleria.png'), fullPage: true });
await page.setViewportSize({ width: 390, height: 844 });
await page.locator('[data-mode="mobile"]').click();
await page.waitForTimeout(300);
if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)) errors.push('gallery mobile overflow');
await browser.close();
if (errors.length) throw new Error(errors.join('\n'));
console.log('Six desktop and mobile previews verified; gallery navigation verified.');
