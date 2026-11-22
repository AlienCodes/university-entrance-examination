// Export both editions from the same title artwork and cover layout.
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require('playwright');
(async () => {
  const dir = __dirname;
  let html = fs.readFileSync(path.join(dir,'cover.html'),'utf8');
  for (const name of ['background.png','headline.png']) {
    const data = fs.readFileSync(path.join(dir,name)).toString('base64');
    html = html.replace('src="'+name+'"','src="data:image/png;base64,'+data+'"');
  }
  const browser = await chromium.launch({executablePath:process.env.CHROME_BIN || '/usr/bin/chromium',args:['--no-sandbox','--disable-dev-shm-usage']});
  try {
    for (const width of [1920,1440]) {
      const page = await browser.newPage({viewport:{width,height:1080},deviceScaleFactor:1});
      await page.setContent(html);
      await page.evaluate(async () => {
        await Promise.all([...document.images].map(image => image.decode()));
        await document.fonts.ready;
      });
      for (const edition of ['20-11','10-1']) {
        await page.locator('#volumes').evaluate((node,value) => {node.textContent=value.replace('-','–');},edition);
        await page.evaluate(() => {
          const blocks = ['.brand','h1 img','.features','.edition'].map(s => document.querySelector(s).getBoundingClientRect());
          if (blocks.some(r=>r.left<0||r.top<0||r.right>innerWidth||r.bottom>innerHeight)) throw Error('Text outside cover');
          if (blocks.some((r,i)=>i>0&&r.top<blocks[i-1].bottom)) throw Error('Overlapping cover text');
        });
        const ratio=width===1920?'16x9':'4x3';
        const file=path.join(dir,'Cambridge-IELTS-'+edition+'-'+ratio+'.jpg');
        await page.screenshot({path:file,type:'jpeg',quality:93});
        if (fs.statSync(file).size>2_000_000) throw Error('Cover exceeds two megabytes');
      }
      await page.close();
    }
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
