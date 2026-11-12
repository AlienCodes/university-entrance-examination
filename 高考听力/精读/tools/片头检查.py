"""老师确认的双行年份/卷名片头检查；不沿用旧封面“标题只能一行”的假设。"""
CHECK = r"""(expected) => {
 const q=s=>document.querySelector(s), out=[];
 const normal=s=>s.replaceAll('Ⅰ','I').replaceAll('Ⅱ','II').replaceAll('Ⅲ','III').replace(/\s/g,'');
 const year=q('.gk-year'), paper=q('.gk-paper'), sub=q('.gk-cover .sub'), small=q('.gk-cover .sub b'), meta=q('.gk-cover .meta');
 if(![year,paper,sub,small,meta].every(Boolean))return ['缺少片头文字块'];
 if(normal(year.innerText+' '+paper.innerText)!==normal(expected))out.push('年份卷名不符');
 if(small.innerText!=='原文精读')out.push('精读标签不符');
 if(!sub.innerText.startsWith('高考英语真题'))out.push('高考题名称不符');
 const fs=e=>parseFloat(getComputedStyle(e).fontSize);
 if(!(fs(year)>fs(sub)&&fs(paper)>fs(sub)&&fs(sub)>fs(small)))out.push('字号层级不符');
 const range=e=>{let r=document.createRange();r.selectNodeContents(e);return r.getBoundingClientRect()};
 let sr=document.createRange();sr.selectNodeContents(sub);if(sub.firstChild)sr.selectNode(sub.firstChild);
 const boxes=[range(year),range(paper),sr.getBoundingClientRect(),range(small),range(meta)];
 boxes.forEach((r,i)=>{if(r.left<60||r.top<40||r.right>1090||r.bottom>innerHeight-40)out.push('文字块'+i+'出界')});
 for(let i=0;i<boxes.length;i++)for(let j=i+1;j<boxes.length;j++){
  let a=boxes[i],b=boxes[j];if(a.left<b.right-2&&b.left<a.right-2&&a.top<b.bottom-2&&b.top<a.bottom-2)out.push('文字块'+i+'/'+j+'重叠');
 }
 if([...document.fonts].some(f=>f.status==='error'))out.push('字体加载失败');
 return out;
}"""


def problems(pg, m, expected):
    return pg.evaluate(CHECK, expected) + m.LC.font_fallback(pg) + [f'字形缺失：{x}' for x in pg.evaluate(m.TH.GLYPH)]
