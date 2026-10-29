import { createRequire } from 'node:module';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

const [url, outDir, packageRoot, browserExecutable] = process.argv.slice(2);
const require = createRequire(path.join(packageRoot, 'package.json'));
const { chromium } = require('playwright-core');
await mkdir(outDir, { recursive: true });
const browser = await chromium.launch({ executablePath: browserExecutable, headless: true,
  args: ['--disable-background-networking', '--no-first-run'] });
const errors = [], dialogs = [], failed = [], external = [];
const page = await browser.newPage({ viewport: { width: 1500, height: 1050 }, locale: 'en-US' });
page.on('pageerror', e => errors.push(e.message));
page.on('dialog', async d => { dialogs.push(d.message()); await d.dismiss(); });
page.on('response', r => { if (r.status() >= 400) failed.push({ url: r.url(), status: r.status() }); });
await page.route('**/*', route => {
  const target = route.request().url();
  if (new URL(target).origin === new URL(url).origin || target.startsWith('data:')) return route.continue();
  external.push(target);
  return route.abort();
});
const results = [];
try {
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForSelector('body[data-ready="true"]', { timeout: 30000 });
  for (const role of ['before', 'after', 'test_cap']) {
    await page.selectOption('#variant', role);
    await page.click('#record');
    await page.waitForFunction(() => ['sent', 'error'].includes(document.querySelector('#status').dataset.phase), { timeout: 60000 });
    const snapshot = await page.evaluate(() => ({ ...window.snubberBridge.getSnapshot(), message: document.querySelector('#status').textContent }));
    if (snapshot.phase !== 'sent') throw new Error(JSON.stringify(snapshot));
    results.push({ role, ...snapshot });
  }
  await page.screenshot({ path: path.join(outDir, 'falstad_connected.png'), fullPage: true });
  // Malformed input must stop in the UI, before posting data.
  await page.fill('#dt_ns', '0');
  await page.click('#record');
  await page.waitForFunction(() => document.querySelector('#status').dataset.phase === 'error');
  const invalidRejected = await page.locator('#status').textContent();
  await page.fill('#dt_ns', '0.5');
  await page.selectOption('#source_mode', 'custom');
  const customControls = await page.evaluate(() => ({
    fieldsDisabled: document.querySelector('#r_ohm').disabled,
    roleRequired: document.querySelector('#variant').value === '',
    contextShown: !document.querySelector('#custom_context_group').hidden
  }));
  if (!customControls.fieldsDisabled || !customControls.roleRequired || !customControls.contextShown) throw new Error('Custom mode did not require explicit inputs');
  if (errors.length || dialogs.length || external.length || failed.length) throw new Error(JSON.stringify({ errors, dialogs, external, failed }));
  await writeFile(path.join(outDir, 'browser_result.json'), JSON.stringify({ results, errors, dialogs, external, failed, invalidRejected, customControls }, null, 2));
  process.stdout.write(JSON.stringify({ ok: true, captures: results.length, errors, dialogs, external, failed }));
} catch (error) {
  await page.screenshot({ path: path.join(outDir, 'falstad_failure.png'), fullPage: true }).catch(() => {});
  await writeFile(path.join(outDir, 'browser_failure.json'), JSON.stringify({ error: String(error), errors, dialogs, failed, external,
    text: await page.locator('body').innerText().catch(() => '') }, null, 2));
  throw error;
} finally {
  await browser.close();
}
