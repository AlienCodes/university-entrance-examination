const DATA=/*__DATA__*/null;
const TIER={core:'★ 高中核心',ext:'☆ 超纲拓展',phr:'◆ 短语搭配'};
const VOICE={female:'女声',male:'男声'};
const $=s=>document.querySelector(s);
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const store={get(k,d){try{const v=localStorage.getItem('gk_'+k);return v==null?d:JSON.parse(v)}catch(e){return d}},set(k,v){try{localStorage.setItem('gk_'+k,JSON.stringify(v))}catch(e){}}};
const P=DATA.passages, byId={}; P.forEach(p=>byId[p.id]=p);
const bankBy={}; DATA.bank.forEach(b=>bankBy[b.h.toLowerCase()]=b);
let known=new Set(store.get('known',[]));
let opt=Object.assign({zh:true,chip:true,hl:true},store.get('opt',{}));
let voice=store.get('voice','female'), rate=store.get('rate',1);
let view='p', cur=store.get('cur',null);
if(!cur||!byId[cur]){const f=P.find(p=>p.done)||P[0];cur=f.id}
const open_=p=>p.done||p.audio;
const short=p=>String(p.year).slice(2)+' '+p.paper.replace(/（(.*?)(·.*?)?）/,'$1')+' '+p.part;
const fmt=t=>{t=Math.max(0,t||0);return Math.floor(t/60)+':'+String(Math.floor(t%60)).padStart(2,'0')};

// ---------------------------------------------------------------- catalog
function catHTML(){
  let h='',sel='<select class="catsel" id="catsel">';
  [...new Set(P.map(p=>p.year))].forEach(y=>{
    h+=`<div class="yr">${y} 年</div>`; sel+=`<optgroup label="${y} 年">`;
    P.filter(p=>p.year===y).forEach(p=>{
      const lbl=`${p.paper} 阅读${p.part}`, ok=open_(p);
      const tag=p.done?`<span class="n">${p.words}词·${p.nv}标</span>`:(p.audio?'<span class="todo">音频 · 标注制作中</span>':'<span class="todo">制作中</span>');
      h+=`<button class="it${p.id===cur&&view==='p'?' on':''}${p.done?'':' todo-it'}" data-id="${p.id}" ${ok?'':'disabled'}>${esc(lbl)}${tag}</button>`;
      sel+=`<option value="${p.id}" ${ok?'':'disabled'} ${p.id===cur?'selected':''}>${esc(y+' '+lbl)}${p.done?'':'（标注制作中）'}</option>`;
    });
    sel+='</optgroup>';
  });
  $('#cat').innerHTML=h;
  const on=$('#cat .it.on'); if(on){const c=$('#cat');c.scrollTop=on.offsetTop-c.clientHeight/2}
  return sel+'</select>';
}
function bindSel(){
  document.querySelectorAll('.it[data-id]').forEach(b=>b.onclick=()=>openP(b.dataset.id));
  const s=$('#catsel'); if(s) s.onchange=()=>openP(s.value);
}

// ---------------------------------------------------------------- sentences
function sentHTML(s){
  const sp=[];s.w.forEach((w,i)=>w.sp.forEach(([a,b])=>sp.push([a,b,w.t,i])));
  sp.sort((x,y)=>x[0]-y[0]);
  let o='',pos=0;
  sp.forEach(([a,b,t,i])=>{if(a<pos)return;o+=esc(s.en.slice(pos,a))+`<mark class="w ${t}" data-h="${esc(s.w[i].h)}" data-m="${esc(s.w[i].m)}" data-t="${t}">${esc(s.en.slice(a,b))}</mark>`;pos=b});
  return o+esc(s.en.slice(pos));
}
function chipsHTML(s){
  return [...s.w].sort((a,b)=>a.sp[0][0]-b.sp[0][0]).map(w=>`<span class="chip ${w.t}"><b>${esc(w.h)}</b>${esc(w.m)}</span>`).join('');
}
function playerHTML(p){
  if(!p.audio) return '';
  const vs=Object.keys(p.audio); if(!p.audio[voice]) voice=vs[0];
  return `<div class="player"><span class="lbl">朗读</span>
   <span class="seg" id="pv">${vs.map(v=>`<button data-v="${v}" class="${v===voice?'on':''}">${VOICE[v]||v}</button>`).join('')}</span>
   <button class="play" id="pp">▶ 播放全文</button>
   <div class="pbar" id="pbar"><i id="pfill"></i></div><span class="ptime" id="ptime">0:00 / ${fmt(p.audio[voice].dur)}</span>
   <span class="seg" id="pr">${[0.75,0.9,1,1.1].map(r=>`<button data-r="${r}" class="${r===rate?'on':''}">${r}×</button>`).join('')}</span></div>`;
}
function renderPassage(){
  const p=byId[cur]; const sel=catHTML();
  let k=0,body='';
  p.paras.forEach(para=>{body+='<div class="para">';para.forEach(s=>{k++;body+=`<div class="s" data-k="${k}"><div class="k" title="播放这一句">${k}</div><div><div class="en">${sentHTML(s)}</div>${s.zh?`<div class="zh">${esc(s.zh)}</div>`:''}${s.w.length?`<div class="chips">${chipsHTML(s)}</div>`:''}</div></div>`});body+='</div>'});
  let head;
  if(p.done){
    const cnt={core:0,ext:0,phr:0};p.paras.flat().forEach(s=>s.w.forEach(w=>cnt[w.t]++));
    head=`<div class="ph"><div class="nm">${esc(p.name)}</div><h1>${esc(p.title)}</h1>
     <div class="meta"><span>${esc(p.genre)}</span><span>全文 <b>${p.words}</b> 词</span><span>${k} 句</span><span>标注 <b>${p.nv}</b> 处（核心 ${cnt.core} · 超纲 ${cnt.ext} · 短语 ${cnt.phr}）</span></div>
     <p class="sum">${esc(p.summary)}</p></div>`;
  }else{
    head=`<div class="ph"><div class="nm">${esc(p.name)}</div><h1>${esc(p.name)}</h1><div class="meta"><span>全文 <b>${p.words}</b> 词</span><span>${k} 句</span></div></div><p class="note">逐句翻译和生词标注制作中，目前可先听原文朗读。</p>`;
  }
  $('#main').innerHTML=sel+`<article class="card">${head}${playerHTML(p)}
  <div class="bar"><button class="tg pri" id="go">▶ 逐句模式</button>
   <button class="tg ${opt.zh?'on':''}" data-o="zh">中文翻译</button><button class="tg ${opt.chip?'on':''}" data-o="chip">句下词表</button><button class="tg ${opt.hl?'on':''}" data-o="hl">高亮</button>
   <span class="legend"><span><i class="dot core"></i>高中核心</span><span><i class="dot ext"></i>超纲拓展</span><span><i class="dot phr"></i>短语搭配</span></span></div>
  <div class="body ${opt.zh?'':'nozh'} ${opt.chip?'':'nochip'} ${opt.hl?'':'nohl'}" id="pb">${body}</div></article>`;
  document.querySelectorAll('[data-o]').forEach(b=>b.onclick=()=>{opt[b.dataset.o]=!opt[b.dataset.o];store.set('opt',opt);renderPassage()});
  $('#go').onclick=()=>openReader(curK()||0);
  bindSel(); bindPlayer(p);
}
function openP(id,flash){
  if(!byId[id]||!open_(byId[id]))return;
  if(id!==cur) stopAudio();
  cur=id;store.set('cur',id);setView('p');window.scrollTo(0,0);
  if(flash){const m=[...document.querySelectorAll('mark.w')].find(x=>x.dataset.h.toLowerCase()===flash);if(m){m.scrollIntoView({block:'center'});m.animate([{outline:'3px solid var(--accent)'},{outline:'3px solid transparent'}],{duration:1600})}}
}

// ---------------------------------------------------------------- audio
const au=new Audio(); au.preload='auto';
let stopAt=null, raf=0, lastK=0;
const A=()=>{const p=byId[cur];return p&&p.audio&&p.audio[voice]};
function ensureSrc(){const a=A();if(!a)return false;const url=encodeURI(a.file);if(!au.src.endsWith(url)){au.src=url}au.playbackRate=rate;return true}
function kAt(t){const a=A();if(!a)return 0;let k=0;for(const [kk,s] of a.s){if(t>=s-0.25)k=kk;else break}return k}
function curK(){return au.src&&!au.paused?kAt(au.currentTime)-1:0}
function playFrom(k,one){
  if(!ensureSrc())return;const a=A();const s=a.s.find(x=>x[0]===k)||a.s[0];
  const go=()=>{au.currentTime=Math.max(0,s[1]-0.05);stopAt=one?s[2]+0.12:null;au.play();tick()};
  if(au.readyState>=1)go();else au.addEventListener('loadedmetadata',go,{once:true});
}
function stopAudio(){au.pause();stopAt=null;cancelAnimationFrame(raf);mark(0)}
function tick(){
  cancelAnimationFrame(raf);
  const step=()=>{
    if(stopAt!==null&&au.currentTime>=stopAt){au.pause();stopAt=null}
    const k=kAt(au.currentTime); if(k!==lastK){mark(k);if($('#rd').classList.contains('on')&&rdAuto&&k>0){rdI=k-1;drawR()}}
    ui(); if(!au.paused) raf=requestAnimationFrame(step); else {ui();if(rdAuto&&au.ended){rdAuto=false;drawR()}}
  };
  raf=requestAnimationFrame(step);
}
function mark(k){
  lastK=k;
  document.querySelectorAll('.s.now').forEach(e=>e.classList.remove('now'));
  if(k){const e=document.querySelector(`.s[data-k="${k}"]`);if(e){e.classList.add('now');if(!au.paused&&stopAt===null){const r=e.getBoundingClientRect();if(r.top<80||r.bottom>innerHeight-20)e.scrollIntoView({block:'center',behavior:'smooth'})}}}
}
function ui(){
  const a=A(); const pp=$('#pp'); if(!a||!pp)return;
  pp.textContent=au.paused?'▶ 播放全文':'⏸ 暂停';
  const d=a.dur, t=au.src.endsWith(encodeURI(a.file))?au.currentTime:0;
  $('#pfill').style.width=(t/d*100)+'%'; $('#ptime').textContent=fmt(t)+' / '+fmt(d);
}
function bindPlayer(p){
  if(!p.audio)return;
  $('#pp').onclick=()=>{if(!ensureSrc())return; if(au.paused){stopAt=null;au.play();tick()}else au.pause(); ui()};
  $('#pbar').onclick=e=>{if(!ensureSrc())return;const r=e.currentTarget.getBoundingClientRect();const go=()=>{au.currentTime=(e.clientX-r.left)/r.width*A().dur;ui();mark(kAt(au.currentTime))};au.readyState>=1?go():au.addEventListener('loadedmetadata',go,{once:true})};
  document.querySelectorAll('#pv button').forEach(b=>b.onclick=()=>{const was=!au.paused,k=kAt(au.currentTime)||1;voice=b.dataset.v;store.set('voice',voice);stopAudio();renderPassage();if(was)playFrom(k,false)});
  document.querySelectorAll('#pr button').forEach(b=>b.onclick=()=>{rate=+b.dataset.r;store.set('rate',rate);au.playbackRate=rate;document.querySelectorAll('#pr button').forEach(x=>x.classList.toggle('on',x===b))});
  document.querySelectorAll('.s .k').forEach(e=>e.onclick=()=>playFrom(+e.parentElement.dataset.k,true));
  ui();
}
au.addEventListener('play',ui);au.addEventListener('pause',ui);

// ---------------------------------------------------------------- word bank
let bq=store.get('bq',{q:'',t:'all',sort:'freq',hide:false});
function renderBank(){
  const sel=catHTML();
  const doneN=P.filter(p=>p.done).length;
  $('#main').innerHTML=sel+`<section class="card">
   <div class="bk-h"><h1>总词库（去重）</h1><p>来自已完成标注的 ${doneN} / ${P.length} 篇文章，共 <b>${DATA.bank.length}</b> 个词条。“出现篇数”统计该词在全部 ${P.length} 篇文章中出现的次数——次数越多越该优先背。勾选表示已掌握。</p></div>
   <div class="bk-c"><input type="search" id="bqq" placeholder="搜索英文或中文…" value="${esc(bq.q)}">
    <select id="bqt"><option value="all">全部类型</option><option value="core">★ 高中核心</option><option value="ext">☆ 超纲拓展</option><option value="phr">◆ 短语搭配</option></select>
    <select id="bqs"><option value="freq">按出现篇数</option><option value="az">按字母 A–Z</option></select>
    <button class="tg ${bq.hide?'on':''}" id="bqh">隐藏已掌握</button><span class="fq" id="bqn"></span></div>
   <div class="rows" id="rows"></div></section>`;
  $('#bqt').value=bq.t;$('#bqs').value=bq.sort;
  const upd=()=>{bq={q:$('#bqq').value,t:$('#bqt').value,sort:$('#bqs').value,hide:bq.hide};store.set('bq',bq);rows()};
  $('#bqq').oninput=upd;$('#bqt').onchange=upd;$('#bqs').onchange=upd;
  $('#bqh').onclick=()=>{bq.hide=!bq.hide;store.set('bq',bq);renderBank()};
  bindSel();rows();
}
function rows(){
  const q=bq.q.trim().toLowerCase();
  let L=DATA.bank.filter(b=>(bq.t==='all'||b.t===bq.t)&&(!q||b.h.toLowerCase().includes(q)||b.m.join('；').includes(q))&&!(bq.hide&&known.has(b.h.toLowerCase())));
  if(bq.sort==='az')L=[...L].sort((a,b)=>a.h.toLowerCase().localeCompare(b.h.toLowerCase()));
  $('#bqn').textContent=L.length+' 条';
  $('#rows').innerHTML=L.length?L.map(b=>{const key=b.h.toLowerCase();return `<div class="row ${known.has(key)?'known':''}"><input type="checkbox" data-k="${esc(key)}" ${known.has(key)?'checked':''} aria-label="已掌握"><div class="hw ${b.t}">${esc(b.h)}</div><div class="mm">${esc(b.m.join('；'))}</div><div class="fq">${b.freq.length} 篇</div><div class="src">${b.freq.slice(0,12).map(id=>`<button data-go="${id}" data-w="${esc(key)}" ${open_(byId[id])?'':'disabled'} title="${esc(byId[id].name)}">${esc(short(byId[id]))}</button>`).join('')}${b.freq.length>12?`<span class="fq">等 ${b.freq.length} 篇</span>`:''}</div></div>`}).join(''):'<div class="empty">没有匹配的词条</div>';
  document.querySelectorAll('.row input').forEach(c=>c.onchange=()=>{c.checked?known.add(c.dataset.k):known.delete(c.dataset.k);store.set('known',[...known]);c.closest('.row').classList.toggle('known',c.checked)});
  document.querySelectorAll('[data-go]').forEach(b=>b.onclick=()=>openP(b.dataset.go,b.dataset.w));
}
function setView(v){view=v;$('#tabP').classList.toggle('on',v==='p');$('#tabB').classList.toggle('on',v==='b');v==='p'?renderPassage():renderBank()}
$('#tabP').onclick=()=>setView('p');$('#tabB').onclick=()=>{stopAudio();setView('b')};

// ---------------------------------------------------------------- popover
const pop=$('#pop');
document.addEventListener('click',e=>{
  const m=e.target.closest('mark.w');
  if(m){const key=m.dataset.h.toLowerCase(),b=bankBy[key];
    pop.innerHTML=`<div class="tier" style="color:var(--${m.dataset.t})">${TIER[m.dataset.t]}</div><h4>${esc(m.dataset.h)}</h4><div class="m">${esc(m.dataset.m)}</div>${b?`<div class="f">在全部 ${P.length} 篇中出现 ${b.freq.length} 篇${b.m.length>1?'；其他释义：'+esc(b.m.filter(x=>x!==m.dataset.m).join('；')):''}</div>`:''}<button class="tg ${known.has(key)?'on':''}" id="pk">${known.has(key)?'✓ 已掌握':'标记为已掌握'}</button>`;
    pop.style.display='block';const r=m.getBoundingClientRect(),w=pop.offsetWidth,h=pop.offsetHeight;
    let x=Math.min(Math.max(8,r.left),innerWidth-w-8),y=r.bottom+8;if(y+h>innerHeight-8)y=r.top-h-8;pop.style.left=x+'px';pop.style.top=y+'px';
    $('#pk').onclick=ev=>{ev.stopPropagation();known.has(key)?known.delete(key):known.add(key);store.set('known',[...known]);pop.style.display='none'};
    e.stopPropagation();return}
  if(!e.target.closest('#pop'))pop.style.display='none';
});

// ---------------------------------------------------------------- reader (逐句模式)
let rdI=0,rdS=[],rdAuto=false,rdO=Object.assign({zh:true,ch:true},store.get('rdo',{}));
function openReader(i){const p=byId[cur];rdS=p.paras.flat();rdI=Math.max(0,i);$('#rdT').textContent=p.name+(p.title?' · '+p.title:'');$('#rd').classList.add('on');document.body.style.overflow='hidden';drawR()}
function drawR(){const s=rdS[rdI];const p=byId[cur];
  $('#rdIn').innerHTML=`<div class="en">${sentHTML(s)}</div>${rdO.zh&&s.zh?`<div class="zh">${esc(s.zh)}</div>`:''}${rdO.ch&&s.w.length?`<div class="chips">${chipsHTML(s)}</div>`:''}`;
  $('#rdPg').textContent=(rdI+1)+' / '+rdS.length;$('#rdP').style.width=((rdI+1)/rdS.length*100)+'%';
  $('#rdZh').classList.toggle('on',rdO.zh);$('#rdCh').classList.toggle('on',rdO.ch);
  $('#rdV').innerHTML=p.audio?Object.keys(p.audio).map(v=>`<button data-v="${v}" class="${v===voice?'on':''}">${VOICE[v]||v}</button>`).join(''):'';
  $('#rdV').style.display=p.audio?'':'none';$('#rdPlay').style.display=p.audio?'':'none';
  $('#rdPlay').textContent=rdAuto?'⏸ 暂停':'▶ 自动播放';
  document.querySelectorAll('#rdV button').forEach(b=>b.onclick=()=>{voice=b.dataset.v;store.set('voice',voice);const was=rdAuto;stopAudio();rdAuto=false;if(was){rdAuto=true;playFrom(rdI+1,false)}drawR()});
}
const closeR=()=>{$('#rd').classList.remove('on');document.body.style.overflow='';if(rdAuto){rdAuto=false;stopAudio()}renderPassage()};
const rdGo=d=>{const n=rdI+d;if(n<0||n>=rdS.length)return;rdI=n;drawR();if(byId[cur].audio){playFrom(rdI+1,!rdAuto)}};
$('#rdPrev').onclick=()=>rdGo(-1);$('#rdNext').onclick=()=>rdGo(1);
$('#rdPlay').onclick=()=>{if(rdAuto){rdAuto=false;au.pause()}else{rdAuto=true;playFrom(rdI+1,false)}drawR()};
$('#rdX').onclick=closeR;
$('#rdZh').onclick=()=>{rdO.zh=!rdO.zh;store.set('rdo',rdO);drawR()};$('#rdCh').onclick=()=>{rdO.ch=!rdO.ch;store.set('rdo',rdO);drawR()};
document.addEventListener('keydown',e=>{if(!$('#rd').classList.contains('on'))return;if(e.key==='ArrowRight'){e.preventDefault();rdGo(1)}else if(e.key==='ArrowLeft')rdGo(-1);else if(e.key===' '){e.preventDefault();$('#rdPlay').click()}else if(e.key==='Escape')closeR()});
setView('p');
