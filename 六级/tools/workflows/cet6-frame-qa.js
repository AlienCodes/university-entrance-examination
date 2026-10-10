export const meta = {
  name: 'cet6-frame-qa',
  description: 'CET-6 finished-video screen QA: every screen of every video inspected by 3 reviewers (layout/numbering, English, Chinese), each finding adversarially verified',
  phases: [
    { title: 'Inspect', detail: '3 reviewers per video: layout & numbering; English & structure; Chinese character by character' },
    { title: 'Verify', detail: '1 skeptical verifier per video re-opens each cited screen' },
  ],
}
// args: {frames: dir with <id>/screenNN.png, ref: dir with <id>.txt, ids: [...]}
const FR = args.frames, REF = args.ref, IDS = args.ids

const FINDING = {
  type: 'object',
  properties: {
    screen: { type: 'integer', description: 'NN of screenNN.png (0 if about the whole video, e.g. a missing screen)' },
    sentence: { type: 'integer', description: 'sentence number k shown/expected on that screen; 0 for the title card or whole video' },
    kind: { type: 'string', enum: ['layout', 'glyph', 'highlight', 'numbering', 'english', 'chinese', 'vocab', 'structure', 'title'] },
    description: { type: 'string', description: 'exactly what is wrong: what the screen shows vs what it should show' },
    severity: { type: 'string', enum: ['high', 'medium', 'low'] },
  },
  required: ['screen', 'sentence', 'kind', 'description', 'severity'],
}
const REPORT = { type: 'object', properties: {
  screens_opened: { type: 'integer', description: 'how many screen images you actually opened and inspected' },
  findings: { type: 'array', items: FINDING }, notes: { type: 'string' } }, required: ['screens_opened', 'findings', 'notes'] }
const VERDICTS = { type: 'object', properties: { verdicts: { type: 'array', items: { type: 'object', properties: {
  index: { type: 'integer' }, real: { type: 'boolean' }, why: { type: 'string' } }, required: ['index', 'real', 'why'] } } }, required: ['verdicts'] }

const CONTEXT = id => `You are checking a FINISHED study video for Chinese university students preparing for CET-6 (大学英语六级, reading Section C). The video was cut into still screens, in playing order: ${FR}/${id}/screen01.png is the title card, screen02.png is sentence 1, and so on (list the folder to see how many). A long sentence may be split across TWO consecutive screens; the cut is marked with "…" at the end of the first part and the start of the second, both screens show the same sentence number, and the vocabulary numbering continues across them.

Design of a sentence screen (this is intended, never report it): header "CET-6 READING", then "<year/month/set> · Passage One/Two" and the Chinese title; the English sentence in a serif font with highlighted vocabulary — dark green bold = single word (单词), rust/brown bold = phrase (短语) — each highlighted item followed by a small numbered circle (a phrase split into pieces carries its number only on its last piece); the Chinese translation below with a grey bar on its left; a VOCABULARY panel on the right listing entries numbered 1, 2, 3 … in order of first appearance, each in the same colour as its highlight, with headword, italic POS for single words (n./v./adj./adv./prep./conj. …; phrases have no POS) and the Chinese meaning; a footer "SENTENCE k / N" with a progress bar and "逐句精读". Font sizes may differ a little between screens (they are auto-fitted), but text must never be cut off or overlap.

The approved reference text is ${REF}/${id}.txt: title, genre, summary; for every sentence [k] its EN, its ZH, and its vocabulary entries ("headword (单词/短语) meaning ← 高亮原文: exact highlighted words"); at the end, the expected number of screens and which sentences are split (with the split point and the two Chinese halves). The text itself has already been reviewed for translation quality — do NOT critique translations or gloss choices; report only where the SCREENS differ from the reference or are visually defective.

Open EVERY screen image (all of them, in order — do not sample, do not stop early) and the reference file. Read-only: do not modify any files.`

const ZOOM = `When anything is small or uncertain, ZOOM IN: crop and enlarge the region with Python, e.g. python3 -c "from PIL import Image; im=Image.open('<screen>'); im.crop((x0,y0,x1,y1)).resize(((x1-x0)*2,(y1-y0)*2)).save('/tmp/<name>.png')" and open the crop (layout: English and Chinese in x≈100–1200, vocabulary panel x≈1230–1830, y≈140–985; footer y≈1000–1050).`
const LENS = {
  visual: `Your job: VISUAL/LAYOUT DEFECTS AND NUMBERING. Procedure for EVERY sentence screen — write these down in your notes as you go, do not just glance: (a) the numbers in the circles in the English, left to right; (b) the numbers in the vocabulary panel, top to bottom; (c) the footer "SENTENCE k / N". Then check: the panel numbers must be consecutive integers in increasing order with no gap, repeat or swap (1,2,3,…; on the second screen of a split they continue from the first screen); the set of circle numbers in the English must equal the set in the panel; every highlighted item has a circle (a split phrase has it only on its last piece) and every panel entry has a highlighted item on that screen; k must be this sentence's number (k increases by 1 from screen to screen, both halves of a split share k) and the progress bar must match k / N. Also look for: text cut off, outside its area, or overlapping anything (header rule, footer, panel, other text); a screen whose font size is abnormal compared with the others; garbled characters, replacement characters (�), empty boxes (tofu), missing glyphs, strange blank gaps inside a line; punctuation drawn in the wrong style (e.g. a Chinese ellipsis …… drawn as six low dots in one place but centred elsewhere); a highlight whose colour does not match its entry type or its panel entry; any other rendering artifact. On the title card, check title, "大学英语六级 <paper> · Passage One/Two" and genre against the reference; check the number and order of screens against the expected structure at the end of the reference. ${ZOOM}`,
  english: `Your job: ENGLISH TEXT, VOCABULARY HEADWORDS AND STRUCTURE vs REFERENCE. For EVERY sentence screen read the English on the screen word by word and compare it with the reference EN: every word, its exact form (singular/plural -s, -ed/-ing endings, a/an/the, similar-looking words like their/there, affect/effect), punctuation and order must be identical — for a split sentence the two screens together must give the whole sentence with nothing missing, added or repeated. For every vocabulary panel entry compare headword and POS (n./v./adj./…; none for phrases) with the reference entry, and check that the words highlighted for it in the English are exactly its 高亮原文. Check the screens cover every sentence exactly once, in order (none missing, duplicated or swapped), and that the title card and every header show the reference title, paper and Passage One/Two. ${ZOOM}`,
  chinese: `Your job: CHINESE TEXT vs REFERENCE, CHARACTER BY CHARACTER. For EVERY sentence screen, zoom into the Chinese translation and transcribe it yourself character by character (do not rely on a glance), then compare with the reference ZH (or the two given halves of a split sentence): every character must match — watch for look-alike wrong characters (形近字, e.g. 全/仝, 日/曰, 己/已, 未/末, 胁/协, 人/入), missing or extra characters, a translation that stops early or belongs to another sentence, and wrong punctuation. Do the same for every Chinese meaning in the vocabulary panel against the reference meanings. Also check the Chinese title on the title card and in the header. ${ZOOM}`,
}
const inspectPrompt = (id, lens) => `${CONTEXT(id)}\n\n${LENS[lens]}\n\nReport every real defect you find with its screen number; if there are none, return an empty list. Do not report the intended design described above.`
const verifyPrompt = (id, fs) => `${CONTEXT(id)}\n\nOther reviewers reported these problems (index: JSON):\n${fs.map((f, i) => `${i}: ${JSON.stringify({ screen: f.screen, sentence: f.sentence, kind: f.kind, description: f.description })}`).join('\n')}\n\nYou are a skeptical verifier. For EACH item, open the cited screen(s) yourself (and neighbouring screens or the reference when needed) and decide whether the problem really exists exactly as described. real=false if you cannot see it, if it is the intended design described above, or if the screen actually matches the reference. Return one verdict per index.`

const LN = ['visual', 'english', 'chinese']
const key = f => `${f.screen}|${f.kind}|${f.description.slice(0, 50)}`
const results = await pipeline(
  IDS,
  async id => {
    const rs = await parallel(LN.map(l => () => agent(inspectPrompt(id, l), { label: `${l}:${id}`, phase: 'Inspect', schema: REPORT })))
    const seen = new Map()
    rs.forEach((r, i) => (r?.findings || []).forEach(f => { const k = key(f); if (!seen.has(k)) seen.set(k, { ...f, lens: LN[i] }) }))
    return { id, findings: [...seen.values()], opened: rs.map(r => r ? r.screens_opened : null), notes: rs.map(r => r ? r.notes : null), failed: rs.filter(r => !r).length }
  },
  async r => {
    if (!r.findings.length) return { ...r, verdicts: [] }
    const v = await agent(verifyPrompt(r.id, r.findings), { label: `verify:${r.id}`, phase: 'Verify', schema: VERDICTS })
    return { ...r, verdicts: v ? v.verdicts : null }
  },
)
const ok = results.filter(Boolean)
const bad = ok.filter(r => r.failed || r.verdicts === null).map(r => r.id)
if (bad.length) log(`incomplete: ${bad.join(', ')}`)
log(`done ${ok.length}; findings ${ok.reduce((s, r) => s + r.findings.length, 0)}`)
return { results: ok, incomplete: bad, missing: IDS.filter(id => !ok.find(r => r.id === id)) }
