export const meta = {
  name: 'batch2-audit-round1',
  description: 'Batch 2 review round 1: 4-lens audit of fresh translations and glosses; double-verify',
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

const CONTEXT = `Context: study materials for Chinese senior-high-school students (gaokao English reading, passages C/D). A video shows each sentence: English (EN), Chinese translation (ZH), and a vocabulary list. Vocabulary line format: headword (tier) gloss ← 高亮原文 = the exact words in EN that are highlighted for this headword. Tiers: 高中核心 (core senior-high word), 超纲拓展 (beyond the syllabus), 短语 (phrase/collocation; phrases have no POS). A single word's gloss = POS + Chinese meaning. The standard is EXTREME precision: the user wants every translation and gloss to be exactly right for a learner. The ZH translations, title, summary and glosses are a FIRST DRAFT that has not been reviewed yet; the English has already had one strict correctness pass (the English as shown is the corrected text that students will study). Review everything with maximum rigour — be as meticulous as on a first pass, check every line, do not assume earlier passes caught everything.
Read-only: do NOT modify any files.`

const LENSES = {
  fidelity: `Your specialty: TRANSLATION FIDELITY — the most important lens: the user insists every Chinese translation match the English exactly. For EVERY sentence compare ZH with EN word by word and clause by clause: omitted information, added meaning, mistranslated words, misread grammar (inversion, relative clauses, what-clauses, passives, comparatives, negation scope, "not…but", "as…as"), wrong tense/aspect or modality (may/might/could/would are hedges and must not become certainties), wrong logical connectors (but/so/because/while), wrong numbers, units, dates, names, quotation boundaries (who said what). Also check degree words and quantifiers (all/most/some/many/few/only/even/still/already/almost/never/rarely), subject/agent (who does what to whom), reference of pronouns (it/this/they), figurative language and idioms rendered with their real meaning, and that nothing in ZH goes beyond what EN says. Also check the passage title and summary are faithful to the passage.`,
  chinese: `Your specialty: CHINESE LANGUAGE QUALITY. For EVERY ZH line, title and summary: typos/wrong characters (错别字), 的/地/得, ungrammatical or unnatural Chinese, ambiguous phrasing, punctuation (Chinese full-width punctuation; correct quotation marks “”; no stray English punctuation), inconsistent transliteration of the same name or term across sentences, inconsistent terminology. Also check the Chinese inside every gloss for typos and wrong characters. Only propose changes that fix a real error or a genuinely confusing/awkward expression, keeping the meaning faithful to EN.`,
  gloss: `Your specialty: VOCABULARY ANNOTATIONS. For EVERY vocabulary line check: (1) the POS matches how the word is used in THIS sentence (noun vs verb vs adjective vs participle-as-adjective, etc.); (2) the Chinese meaning is the sense used in THIS sentence (not just the dictionary's first sense) and is precise; (3) the headword is the correct dictionary form (base form; phrases in standard dictionary form); (4) the highlighted original text really instantiates the headword (a phrase must be fully highlighted, e.g. both parts of not…but also; a highlighted word must actually carry that meaning here); (5) phrases vs single words: single words must not be labelled 短语 and must carry a POS; real multi-word phrases should be 短语; (6) clear tier misclassification only (e.g. a very common core word labelled 超纲拓展 or an obviously advanced/technical word labelled 高中核心). Also check title/genre/summary accuracy.`,
  english: `Your specialty: STRICT CORRECTNESS OF THE ENGLISH (EN lines). The user has ordered that the English be completely correct: any grammar error, spelling error, wrong word, transcription error, or logically confused / self-contradictory / factually wrong statement must be corrected directly in the English with a minimal fix that keeps the author's meaning — EVEN IF the original author or the exam paper wrote it that way ("authentic" is NOT a reason to keep an error). Standard: what a demanding English teacher or professional copy editor preparing texts for students to memorise would mark wrong — e.g. subject–verb or pronoun agreement, tense/aspect (in the past year → present perfect; wish about the past → past perfect), countable/uncountable and articles, faulty parallelism, dangling modifiers, unintended sentence fragments, comma splices, misused idioms, wrong prepositions, numbers or facts that contradict each other. Sentences changed in the previous pass must be checked too (did the fix introduce a new problem?). KEEP (never flag): British spelling/usage, grammatical journalistic style, deliberate fragments in lists/headings, verbatim informal speech inside quotations, numerals at the start of a sentence, the Chinese footnotes in parentheses like "(性别)". Do not rewrite for style. For each error: field "en", "current" = exact erroneous substring copied from the EN line (curly quotes and dashes exactly), "proposed" = replacement substring; in "reason" say whether the ZH line must change and give the new ZH line if so.`,
}

function auditPrompt(pid, lens) {
  return `${CONTEXT}

File: ${DIR}/${pid}.txt — read the WHOLE file and check every line relevant to your specialty.

${LENSES[lens]}

Report ONLY real errors or clearly misleading/awkward items — not stylistic alternatives that are equally correct. If you notice a real error in the English source (EN) while doing your specialty, report it too with field "en". For ZH fixes give the FULL corrected ZH line; for glosses the full corrected gloss (POS + meaning); for summary the corrected sentence(s) with "current" being the exact substring replaced. If everything in your specialty is correct, return an empty list.`
}

function verifyPrompt(pid, findings, lens) {
  const L = lens === 'acc'
    ? `Your lens: ACCURACY. Re-read the EN sentence yourself for each finding. For field "en" findings, accept if the English really is wrong by the strict teacher/copy-editor standard (being the exam's original wording is NOT a reason to keep an error; British usage and grammatical style are not errors) and the replacement is correct, minimal and keeps the author's meaning. Accept if the current text is wrong or misleading and the proposal is correct. If the problem is real but the proposal is imperfect, "amend" with a corrected full text.`
    : `Your lens: NECESSITY AND SAFETY. For each finding decide whether a careful, demanding English teacher would insist on this correction. For field "en" findings: accept if a demanding English teacher or copy editor preparing the text for students to memorise would mark it wrong (being the exam's original wording is NOT a reason to keep an error); reject if it is British usage, grammatical style, or the fix changes the meaning. Reject ONLY if the current text is already accurate and the change is mere taste, or if the proposal introduces a new error/changes meaning, or if "current" does not match the file. If a careful teacher would correct it, accept (or amend).`
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
    const rs = await parallel(['fidelity', 'chinese', 'gloss', 'english'].map(lens => () =>
      agent(auditPrompt(pid, lens), { label: `${lens}:${pid}`, phase: 'Audit', schema: REVIEW })))
    const seen = new Map()
    rs.forEach((r, i) => (r?.findings || []).forEach(f => {
      const k = key(f)
      if (!seen.has(k)) seen.set(k, { ...f, lens: ['fidelity', 'chinese', 'gloss', 'english'][i] })
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
