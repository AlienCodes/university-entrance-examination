export const meta = {
  name: 'tem8-ink-stills-review',
  description: '专八书卷水墨大字版截图盲审：每批一位排版审阅员看全部截图（每批埋 5 个排版雷，审阅员不知道在哪）；漏雷的批次整批重审',
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
const DESIGN = `These are still screens (1920×1080) of 4K study videos for Chinese English majors preparing for TEM-8 (英语专业八级, Reading Section A). Look "书卷水墨" (ink-wash scroll), big-font edition: ALL text is bold (user requirement), the Chinese translation is slightly larger.
- screen01 = cover: dark indigo background with a thin binding strip at the left; a cream paper card with a double-rule border; red letter-spaced caps "TEM-8 · READING · SECTION A"; a red square seal reading 专八 / 精读 (two vertical columns) at the card's top-right; the large bold Chinese title; "英语专业八级 <year>年 · Passage One/Two/Three" (Passage … in blue italic serif); a horizontal rule; genre · topic at the left and "全文 N 词 · 逐句精读" at the right; legend at the bottom right (blue dot 单词, green square 短语).
- every other screen = one sentence on cream paper with a thin indigo strip at the left edge. Header: small red square + "TEM-8 READING" top-left, "<year>年 · Passage X   <Chinese title>" top-right, a double rule under the header. Left: the English sentence in a bold serif (EB Garamond); single words in sky blue (#1f6fd6) followed by a small blue ROUND numbered badge; phrases in green (#2a9142) followed by a small green ROUNDED-SQUARE numbered badge (a phrase split into pieces has its badge only on its last piece). Under the English: the Chinese translation in a bold brush-style (kai) font with a thin grey vertical bar on its left. Right: a tinted "VOCABULARY" panel (red caps label) listing entries with the same badges, the headword in the SAME colour as in the passage (blue words, green phrases), italic POS for single words, then the Chinese meaning. Footer: "SENTENCE k / N" (+ " · PART i/n"), a thin progress line with a small red square marker, and "逐句精读" at the right.
- A long sentence may be split over 2–6 consecutive screens: a grey "…" ends each part and starts the next, the footer shows PART i/n, all parts share the sentence number and the same font sizes, vocabulary numbering continues across parts. Some split sentences deliberately repeat the WHOLE Chinese translation (or a longer Chinese chunk) on several parts when Chinese word order cannot be cut to match the English — that is intended. When Chinese order differs from English, a piece of meaning may appear on a later part than its English words — also intended. BUT report as a defect any part whose Chinese plainly belongs to ANOTHER part's English — the part's own English is translated nowhere on that screen and Chinese word order does not force it (e.g. part 1 shows only the conditional clause while its English already contains the main verb and object; or part 2 pairs \"when tested in a foreign language\" with \"与用母语……相比\"). Check the English/Chinese correspondence of every part of every split sentence.
- Font sizes are auto-fitted per sentence (English is at least 73px at 4K), so they vary a little between sentences.
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
