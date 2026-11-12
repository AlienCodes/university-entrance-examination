export const meta = {
  name: 'ky-stills-review',
  description: '考研晴空校园截图盲审：12 批 × 4 篇，每批一位排版审阅员看全部截图（每批埋 5 个排版雷，审阅员不知道在哪）；漏雷的批次整批重审',
  phases: [
    { title: 'Review', detail: 'one layout reviewer per batch of 4 passages, every screen' },
    { title: 'Re-review', detail: 'batches whose reviewer missed a planted defect are reviewed again from scratch' },
  ],
}
// args: {dir: review copy root with bNN/<pid>/screenNN.jpg and bNN/ref/<pid>.txt, batches: [{batch, passages, mines: [{pid, screen, what}]}]}（mines 只用于计分，不进提示词）
const DIR = args.dir
const FIND = {
  type: 'object',
  properties: {
    findings: { type: 'array', items: { type: 'object', properties: {
      pid: { type: 'string' }, screen: { type: 'string', description: 'like "screen07"' },
      what: { type: 'string', description: 'exactly what is wrong and where on the screen' },
      severity: { type: 'string', enum: ['high', 'medium', 'low'] } }, required: ['pid', 'screen', 'what', 'severity'] } },
    checked: { type: 'integer', description: 'number of screen images you actually opened' },
  },
  required: ['findings', 'checked'],
}
const DESIGN = `These are still screens (1920×1080) of 4K study videos for Chinese students preparing for the postgraduate entrance exam (考研英语, reading Part A). Look "晴空校园" (sunny campus):
- screen01 = cover: sky with clouds and sun, a 985 school building on green hills, a white card with a yellow pill "KAOYAN · READING · PART A", the Chinese title (large rounded font), "<year>年考研英语一/二 · Text N", genre/topic, "全文 N 词 · 逐句精读", legend (blue dot 单词, green square 短语), and an orange round sticker "考研 / 精读" at the card's top-right corner.
- every other screen = one sentence (a long sentence may be split over 2 consecutive screens: "…" ends the first part and starts the second, footer shows PART 1/2 and PART 2/2, both parts share the sentence number, vocabulary numbering continues). Layout: header "KAOYAN READING" pill top-left, paper/Text/title top-right; big white card on the left with the English sentence in bold rounded sans (Nunito), single words in sky blue, phrases in grass green with a yellow marker underline, each highlighted item followed by a small numbered badge (blue circle for words, green rounded square for phrases; a phrase split into pieces has its badge only on its last piece); the Chinese translation in bold black under the English with a yellow bar on its left; a white VOCABULARY card on the right listing entries 1, 2, 3 … (headword in its highlight colour, italic POS for words, Chinese meaning); footer "SENTENCE k / N" (+ " · PART i/2"), a yellow progress bar and "逐句精读".
- Some sentences deliberately show the WHOLE Chinese translation on both parts of a split (when Chinese word order cannot be cut to match the English) — that is intended.
- Font sizes are auto-fitted per sentence, so they vary a little between sentences; the two parts of one split sentence always use the same sizes.
Programs have already measured: overlaps, overflow out of cards/frame, clipping, font fallback/missing glyphs, numbering order, badge spacing, line-break rules (no break inside names, numbers+units, hyphenated words, short Chinese terms, ellipsis+particle, etc.). Your job is what programs cannot judge.`
const reviewPrompt = (b, ps) => `${DESIGN}

You are the LAYOUT REVIEWER for batch ${b}. Read ONLY these files (blind review; do not open anything else, do not search the repository): ${DIR}/${b}/<pid>/screenNN.jpg for pids ${ps.join(', ')} (list each folder; open EVERY screen image in order — do not sample, do not stop early) and the reference texts ${DIR}/${b}/ref/<pid>.txt (what each screen should say).
Look at every screen at full size. Report concrete, screen-specific defects a careful designer or teacher would reject: text overflowing / overlapping / cut off / outside its card; abnormal blank gaps inside a line or a card; text far larger or smaller than on the other screens of the same passage; garbled or wrong characters compared with the reference; tofu boxes or replacement characters (�); badges touching or overlapping letters, squashed or misplaced; punctuation crowding or oddly spaced; English or Chinese breaking in an ugly place (a lone character or word stranded on a line when it could fit, a split right after an opening bracket or before a closing one, a name or number torn apart); a cover whose title, sticker or texts are wrong, overflowing or overlapping the art; anything hard to read on a phone. When something is small or uncertain, ZOOM IN: crop and enlarge with Python, e.g. python3 -c "from PIL import Image; im=Image.open('<screen>'); im.crop((x0,y0,x1,y1)).resize(((x1-x0)*2,(y1-y0)*2)).save('/tmp/${b}_crop.png')" and open the crop.
Do not report consistent matters of taste or the intended design above. Some screens may contain deliberately planted defects — report them like any other defect.
Return every finding (pid, screen like "screen07", what, severity) and the number of screens you opened.`

phase('Review')
const first = await parallel(args.batches.map(x => () =>
  agent(reviewPrompt(x.batch, x.passages), { label: `review-${x.batch}`, phase: 'Review', schema: FIND }).then(r => ({ ...x, r }))))
// 埋雷答案只在 args 里（不进任何提示词）：每批查出几个雷；漏雷或审阅失败的批次整批重审
const sameScreen = (f, m) => f.pid === m.pid && f.screen.replace(/\D/g, '') === m.screen.replace(/\D/g, '')
const score = x => (x.mines || []).filter(m => (x.r?.findings || []).some(f => sameScreen(f, m))).length
first.filter(Boolean).forEach(x => log(`${x.batch}: canaries ${score(x)}/${(x.mines || []).length}, findings ${(x.r?.findings || []).length}, screens opened ${x.r?.checked}`))
const again = first.filter(x => x && (!x.r || score(x) < (x.mines || []).length))
phase('Re-review')
const redo = await parallel(again.map(x => () =>
  agent(reviewPrompt(x.batch, x.passages), { label: `re-review-${x.batch}`, phase: 'Re-review', schema: FIND }).then(r => ({ ...x, r }))))
redo.filter(Boolean).forEach(x => log(`re-review ${x.batch}: canaries ${score(x)}/${(x.mines || []).length}`))
const pack = (x, round) => ({ batch: x.batch, round, passages: x.passages, checked: x.r.checked, caught: score(x), mines: (x.mines || []).length, findings: x.r.findings })
return { results: [...first.filter(x => x && x.r).map(x => pack(x, 1)), ...redo.filter(x => x && x.r).map(x => pack(x, 2))] }
