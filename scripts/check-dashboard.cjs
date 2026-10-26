/* Optional real-browser check. Install Playwright separately as a dev tool. */
const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');

(async () => {
  const base = process.argv[2] || 'http://127.0.0.1:8765';
  const output = path.resolve(process.argv[3] || 'run/browser-check');
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true,
    ...(process.env.TALLYSTICK_CHROMIUM ? { executablePath: process.env.TALLYSTICK_CHROMIUM } : {}) });
  const errors = [];
  const requests = [];
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', request => requests.push(request.url()));
  try {
    await page.goto(base, { waitUntil: 'networkidle' });
    assert.equal(await page.locator('#verified').textContent(), 'Passed');
    assert.equal(await page.locator('#entryCount').textContent(), '20');
    assert.equal(await page.locator('#outcome').textContent(), 'UNDER · 4');
    assert.equal(await page.locator('#timeline li').count(), 6);
    await page.screenshot({ path: path.join(output, 'dashboard-desktop.png'), fullPage: true });
    await page.locator('#timeline button').nth(2).click();
    assert.equal(await page.locator('#outcome').textContent(), 'OVER · 6');
    await page.locator('#stage').fill('3');
    assert.equal(await page.locator('#stageStatus').textContent(), 'pending');
    await page.getByRole('tab', { name: 'Evidence log' }).click();
    assert.equal(await page.locator('#facts tr').count(), 13);
    await page.getByRole('tab', { name: 'Verification', exact: true }).click();
    assert.match(await page.locator('#verificationText').textContent(), /checks passed/);
    const bundle = await page.request.get(base + '/dispute.json');
    assert.equal(bundle.status(), 200);
    assert.equal((await bundle.json()).body.decision.count, 4);
    await page.getByRole('tab', { name: 'Pricing example' }).click();
    assert.match(await page.locator('#pricing').textContent(), /0.593871998/);
    await page.getByRole('tab', { name: 'Settlement replay' }).click();
    await page.locator('#stage').fill('5');
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({ path: path.join(output, 'dashboard-mobile.png'), fullPage: true });
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
      'Mobile page must not overflow horizontally');
    assert.equal(errors.length, 0, errors.join('\n'));
    assert.ok(requests.every(url => url.startsWith(base)), 'Dashboard must be self-contained');
    const receipt = { passed: true, recorded_at: new Date().toISOString(), browser: await browser.version(),
      checks: ['render', 'timeline', 'slider', 'evidence table', 'verification', 'bundle download',
        'pricing', 'mobile overflow', 'no script errors', 'no external page requests'] };
    fs.writeFileSync(path.join(output, 'receipt.json'), JSON.stringify(receipt, null, 2) + '\n');
    console.log(JSON.stringify(receipt, null, 2));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
