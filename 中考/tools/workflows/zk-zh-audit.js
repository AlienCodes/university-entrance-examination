export const meta = {
  name: 'zk-zh-audit',
  description: '中考 translation & annotation audit in groups: 4 specialist reviewers per group of passages, every finding double-verified',
  phases: [
    { title: 'Audit', detail: '4 reviewers per group: translation precision, idiomatic Chinese, vocabulary glosses, whole-passage coherence' },
    { title: 'Verify', detail: '2 independent verifiers per group on merged findings' },
  ],
}
// args: {dir, stage: 'first'|'final', groups: [[id, ...], ...]}
const DIR = args.dir
const GROUPS = args.groups
const STAGE = args.stage || 'first'

const FINDING = {
  type: 'object',
  properties: {
    pid: { type: 'string', description: 'passage file id, e.g. z07' },
    sent: { type: 'integer', description: 'sentence number in [brackets]; 0 for title/genre/summary' },
    field: { type: 'string', enum: ['zh', 'gloss', 'headword', 'add', 'drop', 'title', 'summary', 'genre'] },
    headword: { type: 'string', description: 'for gloss/headword/drop: the headword exactly as listed; otherwise empty' },
    current: { type: 'string', description: 'exact current text: full ZH line / gloss / headword / title / summary substring; for add: empty' },
    proposed: { type: 'string', description: 'full corrected text; for gloss: POS + meaning (no POS for phrases); for headword: new headword; for add: a complete entry in file syntax, e.g. "participant=n. 参与者" or "~take part in=参加"' },
    reason: { type: 'string' },
    severity: { type: 'string', enum: ['high', 'medium', 'low'] },
  },
  required: ['pid', 'sent', 'field', 'headword', 'current', 'proposed', 'reason', 'severity'],
}
const REVIEW = { type: 'object', properties: { findings: { type: 'array', items: FINDING }, notes: { type: 'string' } }, required: ['findings', 'notes'] }
const VERDICTS = { type: 'object', properties: { verdicts: { type: 'array', items: { type: 'object', properties: {
  index: { type: 'integer' }, verdict: { type: 'string', enum: ['accept', 'reject', 'amend'] },
  amended_proposed: { type: 'string' }, why: { type: 'string' } }, required: ['index', 'verdict', 'why'] } } }, required: ['verdicts'] }

const STATUS = STAGE === 'first'
  ? 'The ZH translations, title, summary and glosses are a FIRST DRAFT that has not been reviewed yet. Review everything with maximum rigour; check every line.'
  : 'This text has already been reviewed and corrected; this is a FINAL check. Report ONLY definite errors and clear translationese a native editor would definitely rewrite; do not report refinements of lines that are already accurate and natural. When in doubt, do not report.'
const CONTEXT = `Context: study videos for Chinese JUNIOR-HIGH students (初中生, 14-15) preparing for 中考 who use them to LEARN VOCABULARY (背单词) and understand each sentence of a 中考 English reading passage. The video shows each sentence: English (EN, final — never change it), Chinese translation (ZH), and a vocabulary list. Vocabulary line format: headword (单词 or 短语) gloss ← 高亮原文 = the exact words in EN highlighted for this headword. A single word's gloss = POS + Chinese meaning; phrases have no POS. The user's rules: every Chinese translation must be ABSOLUTELY PRECISE (exactly what the English says) and GENUINELY IDIOMATIC (地道, no translationese), in clear plain Chinese a 14-15-year-old reads easily; every gloss must give the exact sense and POS used in that sentence, in simple Chinese; EVERY word in a sentence that a junior-high learner needs to learn must be annotated (all junior-high curriculum words and above; only primary-school-level and the most common words may be left out). ${STATUS}
Each review covers SEVERAL passage files; report each finding with its passage id ("pid").
Read-only: do NOT modify any files.`

const LENSES = {
  fidelity: `Your specialty: TRANSLATION PRECISION — the most important lens. For EVERY sentence compare ZH with EN clause by clause: omissions, additions, mistranslated words, misread grammar (inversion, relative/what-clauses, passives, comparatives, negation scope, not…but, as…as), wrong tense/aspect or modality (may/might/could are hedges, never certainties; and conversely no hedge may be added), wrong connectors, numbers, units, dates, names, quotation boundaries (who said what; only the speaker's words inside “”), degree words and quantifiers (all/most/some/few/only/even/almost/never), who does what to whom, pronoun referents, idioms rendered with their real meaning. Comparatives: less likely = 可能性更小 (not 不太可能); N times as… = 是……的N倍. Also check that the title and summary are faithful and do not overstate.`,
  chinese: `Your specialty: IDIOMATIC CHINESE (地道). For EVERY ZH line, the title and summary, judge as a top native Chinese translator/editor: flag translationese — English word order, overlong 的-chains or two 的 in a row, unnecessary 被/被…所… passives, 进行+动词, nominalisations, dangling 当……时, literal idioms, unidiomatic collocations, redundant 他/她/它/我们/他们, clumsy connectors, wrong register; also typos/wrong characters (错别字), 的/地/得, punctuation (full-width Chinese punctuation only; “” quotes). Your proposal must be a FULL rewritten ZH line that is more idiomatic AND exactly as precise (no omission/addition, same tense/modality/degree/negation/referents), keeping the Chinese for highlighted phrases recognisable. Do not report mere preferences between equally natural renderings.`,
  gloss: `Your specialty: VOCABULARY ANNOTATIONS. For EVERY vocabulary line: (1) POS matches the use in THIS sentence (participle used as adjective = adj.; gerund = n.); (2) the Chinese meaning is the sense used in THIS sentence and is precise (not an irrelevant dictionary sense); (3) headword in correct dictionary form; (4) the highlighted text really carries that headword/sense (a phrase fully highlighted; not a different word form with a different sense); (5) single words not labelled as phrases, real fixed phrases labelled 短语, free combinations NOT labelled as phrases; (6) MISSING words: any word in the EN sentence that a junior-high learner needs to learn (all junior-high curriculum words and above, useful phrases) but has no entry — report each with field "add" and a complete entry (e.g. "participant=n. 参与者"); (7) useless entries for primary-school-level words every learner knows may be reported with field "drop" only if clearly pointless; (8) glosses must be simple, clear Chinese a 14-year-old understands, giving the sense in this sentence first. Also typos in glosses.`,
  coherence: `Your specialty: WHOLE-PASSAGE COHERENCE, reading the ZH from beginning to end as one Chinese article: consistent rendering of the same names, terms and key concepts in every sentence, title and summary (e.g. one name = one transliteration; one key term = one Chinese term); correct cross-sentence references (这/那/该/其/他们 point to the right thing); connectors between sentences match the English discourse; quotation continuity; the title and summary capture the passage faithfully without overstating; the genre label fits. Give the full corrected ZH line(s) or title/summary text.`,
}

function auditPrompt(g, lens) {
  return `${CONTEXT}\n\nFiles: ${g.map(id => `${DIR}/${id}.txt`).join(', ')} — read EACH WHOLE file and check every line relevant to your specialty in every passage.\n\n${LENSES[lens]}\n\nReport ONLY real errors or clearly misleading/unidiomatic items — not equally good alternatives. For ZH fixes give the FULL corrected ZH line; for glosses the full corrected gloss; for summary "current" = the exact substring replaced and "proposed" = its replacement. If everything in your specialty is correct in a passage, say so in notes.`
}
function verifyPrompt(g, findings, lens) {
  const L = lens === 'acc'
    ? `Your lens: PRECISION. Re-read the EN sentence yourself for each finding (in the file of its pid). Accept if the current text is wrong, imprecise or misleading and the proposal is correct; for idiomatic rewrites accept only if the new line is at least as precise as the old (check every clause) AND clearly more natural; for "add" accept if the word really needs to be learned and the entry (POS + sense) is correct for this sentence. If the problem is real but the proposal is imperfect, "amend" with a corrected full text. Reject if "current" does not match the file.`
    : `Your lens: NATIVE CHINESE EDITOR AND SAFETY. Decide whether a top Chinese translation editor / demanding English teacher would make this change: real imprecision, a wrong gloss/POS, a missing word a junior-high learner must learn, or clearly unnatural Chinese replaced by clearly better, equally precise Chinese. Reject ONLY if the current text is already accurate and natural and the change is mere taste, or if the proposal introduces a new error or changes the meaning.`
  return `${CONTEXT}\n\nFiles: ${g.map(id => `${DIR}/${id}.txt`).join(', ')}\n\nProposed corrections (index: JSON):\n${findings.map((f, i) => `${i}: ${JSON.stringify({ pid: f.pid, sent: f.sent, field: f.field, headword: f.headword, current: f.current, proposed: f.proposed, reason: f.reason })}`).join('\n')}\n\n${L}\nReturn exactly one verdict per index with a short reason.`
}
const key = f => `${f.pid}|${f.sent}|${f.field}|${f.headword}|${(f.current || f.proposed || '').slice(0, 40)}`
const LN = ['fidelity', 'chinese', 'gloss', 'coherence']
const results = await pipeline(
  GROUPS,
  async g => {
    const rs = await parallel(LN.map(l => () => agent(auditPrompt(g, l), { label: `${l}:G${g[0]}`, phase: 'Audit', schema: REVIEW })))
    const seen = new Map()
    rs.forEach((r, i) => (r?.findings || []).forEach(f => { const k = key(f); if (!seen.has(k)) seen.set(k, { ...f, lens: LN[i] }) }))
    return { g, findings: [...seen.values()], failed: rs.filter(r => !r).length }
  },
  async r => {
    if (!r.findings.length) return { ...r, va: [], vb: [] }
    const [a, b] = await parallel(['acc', 'nec'].map(l => () => agent(verifyPrompt(r.g, r.findings, l), { label: `verify-${l}:G${r.g[0]}`, phase: 'Verify', schema: VERDICTS })))
    return { ...r, va: a ? a.verdicts : null, vb: b ? b.verdicts : null }
  },
)
// split each group's findings back into per-passage results (indices renumbered) so the decision script stays the same
const per = []
for (const r of results.filter(Boolean)) {
  for (const id of r.g) {
    const idx = r.findings.map((f, i) => [f, i]).filter(([f]) => f.pid === id)
    const remap = v => v === null ? null : idx.map(([, i], j) => { const x = (v || []).find(y => y.index === i); return x ? { ...x, index: j } : null }).filter(Boolean)
    per.push({ id, findings: idx.map(([f]) => f), va: remap(r.va), vb: remap(r.vb), failed: r.failed })
  }
  const orphan = r.findings.filter(f => !r.g.includes(f.pid))
  if (orphan.length) log(`group ${r.g.join(',')}: ${orphan.length} findings with unknown pid dropped`)
}
const IDS = GROUPS.flat()
const bad = per.filter(r => r.failed || r.va === null || r.vb === null).map(r => r.id)
if (bad.length) log(`incomplete: ${bad.join(', ')}`)
log(`done ${per.length}; findings ${per.reduce((s, r) => s + r.findings.length, 0)}`)
return { results: per, incomplete: bad, missing: IDS.filter(id => !per.find(r => r.id === id)) }
