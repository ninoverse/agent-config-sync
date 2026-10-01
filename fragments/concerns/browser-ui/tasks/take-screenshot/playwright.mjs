/* node .agents/take-screenshot/playwright.mjs <url> <h2-text|""> <out.png> [--clip-children]
 * Entry 1 of take-screenshot. Run from the repo root, directly or through screenshot.sh. */
import { existsSync } from 'node:fs';
import { createRequire } from 'node:module';
import { join } from 'node:path';

const require = createRequire(join(process.cwd(), 'package.json'));
const { chromium } = require('playwright');

const [, , url, heading, out, ...flags] = process.argv;
if (!url || !out) {
    console.error('usage: node playwright.mjs <url> <h2-text|""> <out.png> [--clip-children]');
    process.exit(1);
}
const clipChildren = flags.includes('--clip-children');

const BUNDLED = '/opt/pw-browsers/chromium';
const browser = await chromium.launch({
    ...(existsSync(BUNDLED) ? { executablePath: BUNDLED } : {}),
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
});
const page = await browser.newPage({
    viewport: { width: 1000, height: 900 },
    deviceScaleFactor: 2,
});

/* Change 3: say so when the page asked for web fonts and did not get them. */
const failedFonts = [];
page.on('requestfailed', (request) => {
    if (/fonts\.(googleapis|gstatic)\.com|\.woff2?(\?|$)/.test(request.url())) {
        failedFonts.push(`${request.url().split('?')[0]} (${request.failure()?.errorText})`);
    }
});

/* Change 4: NODE_EXTRA_CA_CERTS marks a TLS-intercepting proxy that Node trusts and Chromium may not,
 * so Google Fonts are fetched from Node there. TLS is still verified, on the Node side. */
if (process.env.NODE_EXTRA_CA_CERTS) {
    await page.route(/^https:\/\/fonts\.(googleapis|gstatic)\.com\//, async (route) => {
        try {
            await route.fulfill({ response: await route.fetch() });
        } catch {
            await route.abort();
        }
    });
}

/* Not `networkidle`: blocked Google Fonts requests keep it from settling. */
await page.goto(url, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(1500);
await page.evaluate(() => document.fonts.ready).catch(() => {});

const findSection = (h) =>
    [...document.querySelectorAll('h2')]
        .find((e) => e.textContent.trim() === h)
        ?.closest('section') ?? null;

/* Change 2: a section with `display: contents` has no box to screenshot. */
const boxless = heading
    ? await page.evaluate((h) => {
          const section = [...document.querySelectorAll('h2')]
              .find((e) => e.textContent.trim() === h)
              ?.closest('section');
          return section ? getComputedStyle(section).display === 'contents' : false;
      }, heading)
    : false;

if (heading && (clipChildren || boxless)) {
    const clip = await page.evaluate((h) => {
        const section = [...document.querySelectorAll('h2')]
            .find((e) => e.textContent.trim() === h)
            ?.closest('section');
        if (!section) return null;
        const boxes = [...section.children].map((c) => c.getBoundingClientRect());
        if (boxes.length === 0) return null;
        const top = Math.min(...boxes.map((b) => b.top)) + window.scrollY;
        const bottom = Math.max(...boxes.map((b) => b.bottom)) + window.scrollY;
        const left = Math.min(...boxes.map((b) => b.left)) + window.scrollX;
        const right = Math.max(...boxes.map((b) => b.right)) + window.scrollX;
        return { x: left - 8, y: top - 8, width: right - left + 16, height: bottom - top + 16 };
    }, heading);
    if (!clip) throw new Error(`no section found for heading "${heading}"`);
    await page.screenshot({ path: out, clip, fullPage: true });
} else if (heading) {
    const handle = await page.evaluateHandle(findSection, heading);
    const element = handle.asElement();
    if (!element) throw new Error(`no section found for heading "${heading}"`);
    await element.screenshot({ path: out });
} else {
    /* Change 1: the whole page, not the first viewport. */
    await page.screenshot({ path: out, fullPage: true });
}

await browser.close();
if (failedFonts.length > 0) {
    console.error(`warning: ${failedFonts.length} web-font request(s) failed, so text renders in a fallback face:`);
    for (const font of failedFonts) console.error(`  ${font}`);
}
console.log('wrote', out);
