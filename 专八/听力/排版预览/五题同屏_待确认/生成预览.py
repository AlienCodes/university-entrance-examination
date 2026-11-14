"""生成用户认可的单屏排版预览；不导入、不修改、不生成任何视频。"""
from pathlib import Path
import hashlib
import base64
import html
import json
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PAPER = ROOT / '专八/听力/批量/数据/2015/试卷.json'
FONTS = ROOT / '专八/听力/fonts_local'


def main():
    p = json.loads(PAPER.read_text())
    group = p['groups'][0]
    qs = {q['n']: q for q in p['questions']}
    escape = lambda s: html.escape(str(s), quote=True)
    rows = []
    for n in group['questions']:
        q = qs[n]
        options = ''.join(
            f'<div class="option" data-n="{n}" data-letter="{letter}">'
            f'<span class="letter">{letter}.</span><span class="text">{escape(text)}</span></div>'
            for letter, text in zip('ABCD', q['options']))
        rows.append(f'<section class="question" data-n="{n}"><div class="number">{n}.</div>'
                    f'<div class="options">{options}</div></section>')
    css = '''
@font-face{font-family:Paper;src:url("FONT_REGULAR");font-weight:400}
@font-face{font-family:Paper;src:url("FONT_BOLD");font-weight:700}
*{box-sizing:border-box}html,body{margin:0;width:1920px;height:1080px;background:#fff;color:#141414}
body{font-family:Paper,"Times New Roman",serif;padding:25px 48px 23px;display:flex;flex-direction:column}
.header{height:65px;flex:none;border-bottom:2px solid #262626;display:flex;align-items:flex-start;justify-content:space-between;gap:24px;margin-bottom:8px}
.heading{font-size:34px;font-weight:700;line-height:1.16;white-space:nowrap;padding-top:4px}
.status{font-family:"Noto Serif CJK SC","Noto Serif SC",serif;font-size:25px;line-height:1.4;white-space:nowrap;padding-top:6px}
.questions{flex:1;min-height:0;display:flex;flex-direction:column;justify-content:space-between;--fs:42px}
.question{display:grid;grid-template-columns:48px minmax(0,1fr);gap:16px;padding:6px 0 7px;border-bottom:2px solid #707780;flex:none}
.question:last-child{border-bottom:0;padding-bottom:0}
.number{font-size:var(--fs);font-weight:700;line-height:1.12}
.options{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);column-gap:36px;row-gap:4px;align-items:start}
.option{display:grid;grid-template-columns:46px minmax(0,1fr);column-gap:6px;font-size:var(--fs);line-height:1.12;align-items:start}
.letter{font-weight:700;white-space:nowrap}.text{white-space:normal;word-break:normal;overflow-wrap:normal;hyphens:none}
'''
    document = '<!doctype html><html lang="en"><meta charset="UTF-8"><style>'+css+'</style><body>'
    document += '<header class="header"><div class="heading">SECTION B&nbsp;&nbsp; INTERVIEW: PART ONE</div>'
    document += '<div class="status">第 1—5 题　｜　采访播放中</div></header>'
    document += '<main class="questions">'+''.join(rows)+'</main></body></html>'
    # 存档仅引用本地字体，字体二进制不嵌入公开仓库；浏览器渲染时临时内嵌。
    archived_document = document.replace('FONT_REGULAR', '../../fonts_local/TimesNewRoman.ttf').replace('FONT_BOLD', '../../fonts_local/TimesNewRomanBold.ttf')
    (HERE/'排版预览.html').write_text(archived_document)
    document = document.replace('FONT_REGULAR', 'data:font/ttf;base64,'+base64.b64encode((FONTS/'TimesNewRoman.ttf').read_bytes()).decode()).replace('FONT_BOLD', 'data:font/ttf;base64,'+base64.b64encode((FONTS/'TimesNewRomanBold.ttf').read_bytes()).decode())
    expected = [{'n':n,'letter':letter,'text':text} for n in group['questions'] for letter,text in zip('ABCD',qs[n]['options'])]
    with sync_playwright() as pw:
        br = pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        pg = br.new_page(viewport={'width':1920,'height':1080},device_scale_factor=2)
        pg.set_content(document,wait_until='load');pg.evaluate('document.fonts.ready')
        result = pg.evaluate('''(expected)=>{
          const main=document.querySelector('.questions'),questions=[...document.querySelectorAll('.question')];
          let chosen=null;
          for(let fs=46;fs>=40;fs--){
            main.style.setProperty('--fs',fs+'px');
            const bound=main.getBoundingClientRect();
            const rects=[...document.querySelectorAll('.question,.option,.letter,.text')].map(x=>x.getBoundingClientRect());
            if(rects.every(x=>x.top>=bound.top-.1&&x.bottom<=bound.bottom+.1&&x.left>=bound.left-.1&&x.right<=bound.right+.1)) {chosen=fs;break;}
          }
          if(chosen===null)throw new Error('完整五题放不下');
          if(questions.map(x=>+x.dataset.n).join(',')!=='1,2,3,4,5')throw new Error('缺题');
          const actual=[...document.querySelectorAll('.option')].map(e=>({n:+e.dataset.n,letter:e.dataset.letter,text:e.querySelector('.text').textContent}));
          if(JSON.stringify(actual)!==JSON.stringify(expected))throw new Error('选项文字/顺序改变');
          const boxes=questions.map(e=>({n:+e.dataset.n,x:e.getBoundingClientRect().x,y:e.getBoundingClientRect().y,height:e.getBoundingClientRect().height}));
          for(let i=1;i<boxes.length;i++)if(boxes[i].y<boxes[i-1].y+boxes[i-1].height-.1)throw new Error('题块重叠');
          return {font_size_css:chosen,output_font_pixels:chosen*2,question_boxes:boxes,questions:5,options:actual.length,all_options_exact:true,layout:'A/B固定上行，C/D固定下行；两栏对齐，每项独立换行缩进'};
        }''', expected)
        pg.screenshot(path=str(HERE/'五题同屏_整齐选项_预览.png'))
        br.close()
    (HERE/'预览说明.json').write_text(json.dumps({'status':'USER_APPROVED_LAYOUT_WITH_REQUESTED_DARKER_SEPARATORS','scope':'用户认可五题同屏固定AB/CD排版；按本轮要求将题间线加深加粗。此目录仅为图片预览，不生成视频；2025保持原样。','separator':{'width_css_px':2,'color':'#707780'},'source_paper':PAPER.relative_to(ROOT).as_posix(),'source_sha256':hashlib.sha256(PAPER.read_bytes()).hexdigest(),'group':group,'pixels':[3840,2160],**result},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':
    main()
