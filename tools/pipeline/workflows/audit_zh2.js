export const meta = {
  name: 'zh-precision-idiom-audit-r2',
  description: 'Translation-focused audit: precision, idiomatic Chinese, whole-passage coherence, glosses; double-verify',
  phases: [
    { title: 'Audit', detail: '4 specialist reviewers per passage: translation fidelity, Chinese quality, vocabulary glosses, English source errors' },
    { title: 'Verify', detail: '2 independent verifiers per passage on the merged findings' },
  ],
}

const DIR = args.dir
const PIDS = args.pids

const FINDING = {
  type: 'object',
  properties: {
    sent: { type: 'integer', description: 'sentence number in [brackets]; 0 for title/genre/summary' },
    field: { type: 'string', enum: ['zh', 'gloss', 'headword', 'tier', 'title', 'summary', 'genre', 'en'] },
    headword: { type: 'string', description: 'for gloss/headword/tier: the headword exactly as listed; otherwise empty' },
    current: { type: 'string', description: 'exact current text (full ZH line / gloss / headword / tier label / title / summary sentence; for en: the exact erroneous substring of the EN sentence, long enough to be unique in that sentence)' },
    proposed: { type: 'string', description: 'full corrected text; for tier one of 高中核心 / 超纲拓展 / 短语; for en: the replacement substring' },
    reason: { type: 'string' },
    severity: { type: 'string', enum: ['high', 'medium', 'low'] },
  },
  required: ['sent', 'field', 'headword', 'current', 'proposed', 'reason', 'severity'],
}
const REVIEW = { type: 'object', properties: { findings: { type: 'array', items: FINDING }, notes: { type: 'string' } }, required: ['findings', 'notes'] }
const VERDICTS = {
  type: 'object',
  properties: { verdicts: { type: 'array', items: { type: 'object', properties: {
    index: { type: 'integer' }, verdict: { type: 'string', enum: ['accept', 'reject', 'amend'] },
    amended_proposed: { type: 'string' }, why: { type: 'string' } }, required: ['index', 'verdict', 'why'] } } },
  required: ['verdicts'],
}

const CONTEXT = `Context: study materials for Chinese senior-high-school students (gaokao English reading, passages C/D). A video shows each sentence: English (EN), Chinese translation (ZH), and a vocabulary list. Vocabulary line format: headword (tier) gloss ← 高亮原文 = the exact words in EN that are highlighted for this headword. Tiers: 高中核心 (core senior-high word), 超纲拓展 (beyond the syllabus), 短语 (phrase/collocation; phrases have no POS). A single word's gloss = POS + Chinese meaning. The standard is EXTREME precision: the user wants every translation and gloss to be exactly right for a learner. This text has already had four review passes, the last one specifically for precision and idiomatic Chinese, and is believed correct. The user now demands that every Chinese translation be (1) ABSOLUTELY PRECISE and (2) GENUINELY IDIOMATIC (地道) — natural Chinese a skilled native translator would write, with no translationese (翻译腔). Read it as a top-tier translator and editor would; look for anything still imprecise or not idiomatic — be as meticulous as on a first pass, check every line, do not assume earlier passes caught everything.
Read-only: do NOT modify any files.`

const LENSES = {
  fidelity: `Your specialty: TRANSLATION PRECISION — the most important lens: the user insists every Chinese translation match the English exactly. For EVERY sentence compare ZH with EN word by word and clause by clause: omitted information, added meaning, mistranslated words, misread grammar (inversion, relative clauses, what-clauses, passives, comparatives, negation scope, "not…but", "as…as"), wrong tense/aspect or modality (may/might/could/would are hedges and must not become certainties), wrong logical connectors (but/so/because/while), wrong numbers, units, dates, names, quotation boundaries (who said what). Also check degree words and quantifiers (all/most/some/many/few/only/even/still/already/almost/never/rarely), subject/agent (who does what to whom), reference of pronouns (it/this/they), figurative language and idioms rendered with their real meaning, and that nothing in ZH goes beyond what EN says. Also check the passage title and summary are faithful to the passage.`,
  chinese: `Your specialty: IDIOMATIC CHINESE (地道). For EVERY ZH line, the title and the summary, judge as a skilled native Chinese translator/editor: is it natural, fluent Chinese that reads as if originally written in Chinese? Flag translationese (翻译腔): English word order copied into Chinese, overlong 的-chains, stacked or unnecessary 被 passives, dangling 当……时 frames, unnatural noun-heavy phrasing, literal renderings of idioms/metaphors, unidiomatic collocations (动宾/修饰搭配不当), pronoun overuse (他/她/它们/我们 repeated where Chinese would omit), clumsy connectors, wrong register, awkward rhythm. Also typos, 的/地/得, punctuation. Your proposal must be a FULL rewritten ZH line that is BOTH more idiomatic AND exactly as precise as the English (no omissions, no additions, same tense/modality/degree/negation/referents); keep wording that maps to highlighted glossed phrases recognisable. Do not report lines that are already natural and precise; do not report mere personal preferences between two equally natural renderings.`,
  gloss: `Your specialty: VOCABULARY ANNOTATIONS. For EVERY vocabulary line check: (1) the POS matches how the word is used in THIS sentence (noun vs verb vs adjective vs participle-as-adjective, etc.); (2) the Chinese meaning is the sense used in THIS sentence (not just the dictionary's first sense) and is precise; (3) the headword is the correct dictionary form (base form; phrases in standard dictionary form); (4) the highlighted original text really instantiates the headword (a phrase must be fully highlighted, e.g. both parts of not…but also; a highlighted word must actually carry that meaning here); (5) phrases vs single words: single words must not be labelled 短语 and must carry a POS; real multi-word phrases should be 短语; (6) clear tier misclassification only (e.g. a very common core word labelled 超纲拓展 or an obviously advanced/technical word labelled 高中核心). Also check title/genre/summary accuracy.`,
  coherence: `Your specialty: WHOLE-PASSAGE COHERENCE, read from beginning to end as one text: the ZH lines must read as one coherent Chinese article — consistent rendering of the same names, terms and key concepts in every sentence (and in title/summary); correct cross-sentence reference (这/那/该/其/他们 point to the right thing); logical connectors between sentences match the English discourse; quotation continuity across sentences; the title and summary faithfully capture the passage without overstating; the genre label fits. Also report any remaining error in the English itself (field "en") if you notice one. For each issue give the full corrected ZH line(s) or summary/title text.`,
}

function auditPrompt(pid, lens) {
  return `${CONTEXT}

File: ${DIR}/${pid}.txt — read the WHOLE file and check every line relevant to your specialty.

${LENSES[lens]}

Report ONLY real errors or clearly misleading/awkward items — not stylistic alternatives that are equally correct. If you notice a real error in the English source (EN) while doing your specialty, report it too with field "en". For ZH fixes give the FULL corrected ZH line; for glosses the full corrected gloss (POS + meaning); for summary the corrected sentence(s) with "current" being the exact substring replaced. If everything in your specialty is correct, return an empty list.`
}

function verifyPrompt(pid, findings, lens) {
  const L = lens === 'acc'
    ? `Your lens: PRECISION. For idiomatic-Chinese rewrites, accept only if the new line is at least as precise as the English as the old one (check every clause) AND clearly more natural Chinese; amend if the idea is right but the rewrite loses or adds meaning. Re-read the EN sentence yourself for each finding. For field "en" findings, accept if the English really is wrong by the strict teacher/copy-editor standard (being the exam's original wording is NOT a reason to keep an error; British usage and grammatical style are not errors) and the replacement is correct, minimal and keeps the author's meaning. Accept if the current text is wrong or misleading and the proposal is correct. If the problem is real but the proposal is imperfect, "amend" with a corrected full text.`
    : `Your lens: NATIVE CHINESE EDITOR AND SAFETY. The user explicitly wants translations that are both exact and genuinely idiomatic, so translationese IS a defect to fix. For each finding decide whether a top Chinese translation editor would make this change (real imprecision, or clearly unnatural/translationese Chinese replaced by clearly better, equally precise Chinese). For field "en" findings: accept if a demanding English teacher or copy editor preparing the text for students to memorise would mark it wrong (being the exam's original wording is NOT a reason to keep an error); reject if it is British usage, grammatical style, or the fix changes the meaning. Reject ONLY if the current text is already accurate and the change is mere taste, or if the proposal introduces a new error/changes meaning, or if "current" does not match the file. If a careful teacher would correct it, accept (or amend).`
  return `${CONTEXT}

File: ${DIR}/${pid}.txt

Proposed corrections (index: JSON):
${findings.map((f, i) => `${i}: ${JSON.stringify(f)}`).join('\n')}

${L}
Return exactly one verdict per index with a short reason.`
}

const key = f => `${f.sent}|${f.field}|${f.headword}|${(f.current || '').slice(0, 40)}`

const results = await pipeline(
  PIDS,
  async pid => {
    const rs = await parallel(['fidelity', 'chinese', 'gloss', 'coherence'].map(lens => () =>
      agent(auditPrompt(pid, lens), { label: `${lens}:${pid}`, phase: 'Audit', schema: REVIEW })))
    const seen = new Map()
    rs.forEach((r, i) => (r?.findings || []).forEach(f => {
      const k = key(f)
      if (!seen.has(k)) seen.set(k, { ...f, lens: ['fidelity', 'chinese', 'gloss', 'coherence'][i] })
    }))
    return { pid, findings: [...seen.values()], notes: rs.map(r => r?.notes || '') }
  },
  async (r) => {
    if (!r.findings.length) return { pid: r.pid, kept: [], dropped: [], notes: r.notes }
    const [a, b] = await parallel([
      () => agent(verifyPrompt(r.pid, r.findings, 'acc'), { label: `verify-acc:${r.pid}`, phase: 'Verify', schema: VERDICTS }),
      () => agent(verifyPrompt(r.pid, r.findings, 'nec'), { label: `verify-nec:${r.pid}`, phase: 'Verify', schema: VERDICTS }),
    ])
    const va = new Map((a?.verdicts || []).map(v => [v.index, v]))
    const vb = new Map((b?.verdicts || []).map(v => [v.index, v]))
    const kept = [], dropped = []
    r.findings.forEach((f, i) => {
      const x = va.get(i), y = vb.get(i)
      const g = { ...f, pid: r.pid }
      if (!x || !y || x.verdict === 'reject' || y.verdict === 'reject') {
        dropped.push({ ...g, votes: [x?.verdict, y?.verdict], why: [x?.why, y?.why] }); return
      }
      const prop = (x.verdict === 'amend' && x.amended_proposed) || (y.verdict === 'amend' && y.amended_proposed) || f.proposed
      kept.push({ ...g, proposed: prop, original_proposed: f.proposed, why: [x.why, y.why] })
    })
    return { pid: r.pid, kept, dropped, notes: r.notes }
  },
)
const ok = results.filter(Boolean)
const kept = ok.flatMap(r => r.kept), dropped = ok.flatMap(r => r.dropped)
log(`kept ${kept.length}, dropped ${dropped.length}`)
return { kept, dropped, notes: ok.map(r => ({ pid: r.pid, notes: r.notes })) }
