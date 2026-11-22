const fs=require('node:fs'), path=require('node:path');
const {chromium}=require('playwright');
(async()=>{
 const root=__dirname, template=fs.readFileSync(path.join(root,'cover.html'),'utf8');
 const browser=await chromium.launch({executablePath:process.env.CHROME_BIN||'/usr/bin/chromium',args:['--no-sandbox','--disable-dev-shm-usage']});
 try{
  for(const theme of ['red','blue']){
   const art=theme==='blue'?'ultramarine.png':'vermilion.png';
   const data='data:image/png;base64,'+fs.readFileSync(path.join(root,art)).toString('base64');
   for(const width of [1920,1440]){
    const page=await browser.newPage({viewport:{width,height:1080},deviceScaleFactor:1});
    await page.route('http://127.0.0.1/editorial-cover/**',route=>{
      const u=new URL(route.request().url());
      if(u.pathname.endsWith('.html'))return route.fulfill({contentType:'text/html; charset=utf-8',body:template});
      if(u.pathname.endsWith('/'+art))return route.fulfill({contentType:'image/png',body:Buffer.from(data.split(',')[1],'base64')});
      return route.fulfill({status:404,body:''});
    });
    for(const edition of ['20-11','10-1']){
     await page.goto('http://127.0.0.1/editorial-cover/cover.html?theme='+theme+'&edition='+edition);
     await page.evaluate(async()=>{await document.fonts.ready;await document.querySelector('#art').decode();});
     await page.evaluate(()=>{
      const blocks=['.brand span','.lead','.noun','.via','.method strong','.features span','.range','.count'];
      const rects=blocks.flatMap(s=>[...document.querySelectorAll(s)].map(e=>[e.textContent,e.getBoundingClientRect()]));
      for(const [text,r] of rects){if(r.left<0||r.top<0||r.right>innerWidth||r.bottom>innerHeight)throw Error(text+' clipped');}
      for(let i=0;i<rects.length;i++)for(let j=i+1;j<rects.length;j++){
       const a=rects[i][1],b=rects[j][1];
       if(Math.min(a.right,b.right)-Math.max(a.left,b.left)>1&&Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)>1)throw Error(rects[i][0]+' overlaps '+rects[j][0]);
      }
     });
     const f=path.join(root,'Cambridge-IELTS-'+edition+'-'+(width===1920?'16x9':'4x3')+(theme==='blue'?'-Blue':'')+'.jpg');
     await page.screenshot({path:f,type:'jpeg',quality:94});
     if(fs.statSync(f).size>2_000_000)throw Error('oversize '+f);
    }
    await page.close();
   }
  }
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
