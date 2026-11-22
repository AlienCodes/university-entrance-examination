// Run in a Node environment with Playwright, Chromium and Noto Sans CJK SC.
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require('playwright');

(async () => {
  const template = fs.readFileSync(path.join(__dirname, 'cover.html'), 'utf8');
  const editions = {'20-11': 'book.png', '10-1': 'book-10.png'};
  const browser = await chromium.launch({
    executablePath: process.env.CHROME_BIN || '/usr/bin/chromium',
    args: ['--no-sandbox', '--disable-dev-shm-usage']
  });
  try {
    for (const width of [1920, 1440]) {
      const page = await browser.newPage({viewport: {width, height: 1080}, deviceScaleFactor: 1});
      for (const [edition, illustration] of Object.entries(editions)) {
        const book = fs.readFileSync(path.join(__dirname, illustration)).toString('base64');
        await page.setContent(template.replace('src="book.png"', 'src="data:image/png;base64,' + book + '"'));
        await page.locator('#volumes').evaluate((node, value) => {
          node.textContent = value.replace('-', '–');
        }, edition);
        await page.evaluate(async () => {
          await document.fonts.ready;
          await document.querySelector('.book').decode();
          for (const label of document.querySelectorAll('.subject,.method,.kicker,.features,.edition')) {
            const r = label.getBoundingClientRect();
            if (r.left < 0 || r.right > innerWidth || r.top < 0 || r.bottom > innerHeight) {
              throw new Error('Cover text clipped: ' + label.textContent);
            }
          }
        });
        const ratio = width === 1920 ? '16x9' : '4x3';
        const output = path.join(__dirname, 'Cambridge-IELTS-' + edition + '-' + ratio + '.jpg');
        await page.screenshot({path: output, type: 'jpeg', quality: 94});
        if (fs.statSync(output).size > 2_000_000) throw new Error('Cover exceeds two megabytes');
      }
      await page.close();
    }
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
