export const meta = {
  name: 'ky-final-check',
  description: 'Round 2 final check of the corrected 48 kaoyan Reading Part A texts + 2 new canaries, one batch per exam paper: 2 finders + 2 verifiers per batch',
  phases: [
    { title: 'Find', detail: '2 independent final-check reviewers per paper: form (spelling/punctuation/grammar) and meaning (+ the round-1 corrections)' },
    { title: 'Verify', detail: '2 independent verifiers per paper on merged findings: accuracy, strict editor' },
  ],
}
// 第二轮终查（由 ky-proofread.js 改写）。args: { dir, batches: [[ids...], ...] }  — 每批 = 一份试卷的 4 篇（新的埋雷副本混在别的试卷的批里）
// 考研试卷都是文字版 PDF，原文取自文字层，不派人对照图片逐字核对（与专八不同，见 考研/tools/gen_proof.py）。
const DIR = args.dir
const BATCHES = args.batches

const FINDING = {
  type: 'object',
  properties: {
    id: { type: 'string', description: 'passage id, e.g. k07 (from the file name)' },
    loc: { type: 'string', description: 'paragraph and sentence like ¶3 s2' },
    current: { type: 'string', description: 'exact substring of the CURRENT text, copied character for character (curly quotes ’ “ ”, em dash —), long enough to be unique in the whole passage' },
    proposed: { type: 'string', description: 'replacement for that substring (minimal fix)' },
    category: { type: 'string', enum: ['spelling', 'punctuation', 'typography', 'grammar', 'word-choice', 'logic', 'fact', 'bad-correction'] },
    reason: { type: 'string' },
    severity: { type: 'string', enum: ['high', 'medium', 'low'] },
  },
  required: ['id', 'loc', 'current', 'proposed', 'category', 'reason', 'severity'],
}
const REVIEW = { type: 'object', properties: { findings: { type: 'array', items: FINDING }, notes: { type: 'string' } }, required: ['findings', 'notes'] }
const VERDICTS = {
  type: 'object',
  properties: { verdicts: { type: 'array', items: { type: 'object', properties: {
    index: { type: 'integer' }, verdict: { type: 'string', enum: ['accept', 'reject', 'amend'] },
    amended_proposed: { type: 'string', description: 'for amend: the corrected replacement substring' },
    why: { type: 'string' } }, required: ['index', 'verdict', 'why'] } } },
  required: ['verdicts'],
}

const CONTEXT = `Context: reading passages (Section II Reading Comprehension, Part A, Text 1–4) from China's national postgraduate entrance examination English papers (考研英语一 / 英语二), 2021–2026. They are adapted from English-language journalism (The Economist, The Guardian, The Atlantic, Financial Times, Scientific American, etc.). Chinese students will study, memorise and recite these texts sentence by sentence, so the English must be COMPLETELY CORRECT. The text was taken from the exam PDFs' text layer, so it matches the printed paper; your job is to find errors IN THE PRINTED PAPER ITSELF (or in our few listed corrections): spelling, grammar, punctuation, wrong word, wrong idiom, logical contradiction, factual impossibility, a word broken by typesetting. These must be corrected: a sentence that a careful English teacher or professional copy editor would mark wrong must be fixed EVEN IF the exam paper printed it that way ("it is the exam's original wording" is NOT a reason to keep an error). Use a minimal fix that keeps the author's meaning.
THIS IS THE SECOND, FINAL ROUND: the texts were already proofread once and corrected (the corrections are listed in each file header). Report ONLY definite errors that a careful English teacher would mark wrong — not style preferences, optional commas or rewrites of correct English. Also check each listed correction: is it right, minimal, and does it fit the sentence (category bad-correction)?
KEEP (never flag): British spelling and usage (realise, whilst, in hospital, Dr without a full stop, collective nouns with plural verbs, punctuation outside quotes); American spelling; mixing of the two across different passages; legitimate journalistic style that is grammatical (deliberate fragments, inversion, ellipsis, headline-style phrasing); informal but standard spoken English inside quotations; the house style listed in the file header (版式约定); items the header lists as already decided (已决定不改) unless you have a new, definite reason. Do NOT rewrite for style or "improve" correct English — only report what is actually wrong. Do not report differences already listed in the file header as corrected on purpose (已经做过的订正) — but DO report if such a correction is itself wrong.
Read-only: do NOT modify any files. You may use web search to find the original source article to check a suspected error (the exam often adapts its source; only an adaptation that introduced an ERROR counts).`

const LENSES = {
  form: `Your focus: FORM. Go through EVERY sentence of every passage, character by character: spelling (including real words used wrongly: homophones and near-homophones such as their/there, beside/besides, hole/whole, mane/main, portion/potion), punctuation (comma splices, run-ons, misplaced semicolons/colons, quotation marks, apostrophes, hyphens in compound modifiers), and grammar (agreement, including long and compound subjects and "along with"; tense and sequence of tenses; verb forms and patterns, a missing "to"; articles and countability; pronoun reference and agreement; relative pronouns who/which; question word order; parallelism; comparatives; prepositions; dangling or misplaced modifiers; fragments).`,
  meaning: `Your focus: MEANING. Go through EVERY sentence: wrong word or collocation, wrong idiom, misused connectors (but/so/however — e.g. "but" joining two ideas that do not contrast), statements contradicting the rest of the passage (up vs down, increase vs decrease, only + a large share), impossible numbers/dates/facts, unclear or wrong pronoun reference that changes meaning; and examine EACH correction listed in the file header — is it right, minimal, and does it fit the sentence? Also report any clear spelling/grammar/punctuation error you notice.`,
}

const files = ids => ids.map(id => `${DIR}/${id}.txt`).join('\n')

function findPrompt(ids, lens) {
  return `${CONTEXT}

Files (${ids.length} passages — read EVERY file completely, including the header lines; treat each passage separately):
${files(ids)}

${LENSES[lens]}

Report each real error with the passage id and the minimal fix ("current" = exact substring of the current text of that passage, "proposed" = replacement). If a passage has nothing, say so in notes and list the sentences you examined most closely.`
}

function verifyPrompt(ids, findings, lens) {
  const L = lens === 'acc'
    ? `Your lens: ACCURACY. For each proposed fix: open the passage file, read the sentence and its context yourself. Accept if the current text is genuinely wrong by the standard above and the replacement is correct, minimal and keeps the meaning. If the error is real but the replacement is imperfect (not minimal, introduces a new problem), "amend" with a better replacement. Reject if the current text is actually correct, the finding is a style preference, British usage, house style, or a difference already corrected on purpose, or "current" does not occur exactly in that passage.`
    : `Your lens: STRICT EDITOR. For each proposed fix decide: would a demanding English teacher or professional copy editor preparing these texts for students to memorise mark the current wording as an error? If yes, accept (or amend if the fix is not the best minimal one). Do NOT reject merely because the exam paper printed it that way — that is explicitly not a reason to keep an error. Reject only if the current text is correct, the change is pure style, it would change the author's meaning, or "current" does not match the text exactly.`
  return `${CONTEXT}

Passage files:
${files(ids)}

Proposed corrections (index: JSON; "id" names the passage):
${findings.map((f, i) => `${i}: ${JSON.stringify(f)}`).join('\n')}

${L}
Return exactly one verdict per index with a short reason.`
}

const key = f => `${f.id}|${(f.current || '').toLowerCase().replace(/\s+/g, ' ').slice(0, 40)}`
const LENS_NAMES = ['form', 'meaning']

const results = await pipeline(
  BATCHES,
  async (ids, _, bi) => {
    const rs = await parallel(LENS_NAMES.map(lens => () =>
      agent(findPrompt(ids, lens), { label: `${lens}:b${bi + 1}`, phase: 'Find', schema: REVIEW })))
    const seen = new Map()
    rs.forEach((r, i) => (r?.findings || []).forEach(f => {
      const k = key(f)
      if (!seen.has(k)) seen.set(k, { ...f, lens: [LENS_NAMES[i]] })
      else if (!seen.get(k).lens.includes(LENS_NAMES[i])) seen.get(k).lens.push(LENS_NAMES[i])
    }))
    return { ids, bi, findings: [...seen.values()], notes: Object.fromEntries(rs.map((r, i) => [LENS_NAMES[i], r ? r.notes : 'AGENT FAILED'])), failed: rs.map((r, i) => r ? null : LENS_NAMES[i]).filter(Boolean) }
  },
  async r => {
    if (!r.findings.length) return { ...r, kept: [], dropped: [] }
    const [a, b] = await parallel([
      () => agent(verifyPrompt(r.ids, r.findings, 'acc'), { label: `verify-acc:b${r.bi + 1}`, phase: 'Verify', schema: VERDICTS }),
      () => agent(verifyPrompt(r.ids, r.findings, 'strict'), { label: `verify-strict:b${r.bi + 1}`, phase: 'Verify', schema: VERDICTS }),
    ])
    const va = new Map((a?.verdicts || []).map(v => [v.index, v]))
    const vb = new Map((b?.verdicts || []).map(v => [v.index, v]))
    const kept = [], dropped = []
    r.findings.forEach((f, i) => {
      const x = va.get(i), y = vb.get(i)
      const g = { ...f, votes: [x?.verdict, y?.verdict], why: [x?.why, y?.why], amended: [x?.amended_proposed || '', y?.amended_proposed || ''] }
      if (!x || !y || x.verdict === 'reject' || y.verdict === 'reject') dropped.push(g)
      else kept.push(g)
    })
    return { ...r, kept, dropped, verify_failed: [a ? null : 'acc', b ? null : 'strict'].filter(Boolean) }
  },
)
const ok = results.filter(Boolean)
const failed = ok.filter(r => r.failed.length || (r.verify_failed || []).length).map(r => ({ batch: r.bi + 1, find: r.failed, verify: r.verify_failed || [] }))
const missing = BATCHES.map((_, i) => i).filter(i => !ok.find(r => r.bi === i))
if (failed.length || missing.length) log(`FAILED: ${JSON.stringify(failed)} missing batches ${missing.map(i => i + 1).join(',')}`)
const kept = ok.flatMap(r => r.kept), dropped = ok.flatMap(r => r.dropped)
log(`kept ${kept.length}, dropped ${dropped.length}`)
return { kept, dropped, failed, missing, notes: ok.map(r => ({ batch: r.bi + 1, ids: r.ids, notes: r.notes })) }
