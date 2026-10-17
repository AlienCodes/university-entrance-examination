export const meta = {
  name: 'zk-final-check',
  description: '中考 reading round 2: final check of the corrected passages (+canaries) in groups, 2 finders + 2 verifiers per group',
  phases: [
    { title: 'Find', detail: '2 independent final-check reviewers per group of passages' },
    { title: 'Verify', detail: '2 independent verifiers per group with findings' },
  ],
}
// args: {dir, groups: [[id, ...], ...]}
const DIR = args.dir
const GROUPS = args.groups
const FINDING = {
  type: 'object',
  properties: {
    pid: { type: 'string', description: 'passage file id, e.g. z07' },
    loc: { type: 'string' },
    current: { type: 'string', description: 'exact substring of the CURRENT text, character for character (curly quotes ’ “ ”, em dash —), unique in the passage' },
    proposed: { type: 'string', description: 'minimal replacement for that substring' },
    category: { type: 'string', enum: ['spelling', 'punctuation', 'typography', 'grammar', 'word-choice', 'logic', 'fact', 'bad-correction'] },
    reason: { type: 'string' },
  },
  required: ['pid', 'loc', 'current', 'proposed', 'category', 'reason'],
}
const REVIEW = { type: 'object', properties: { findings: { type: 'array', items: FINDING }, notes: { type: 'string' } }, required: ['findings', 'notes'] }
const VERDICTS = { type: 'object', properties: { verdicts: { type: 'array', items: { type: 'object', properties: {
  index: { type: 'integer' }, verdict: { type: 'string', enum: ['accept', 'reject', 'amend'] },
  amended_proposed: { type: 'string' }, why: { type: 'string' } }, required: ['index', 'verdict', 'why'] } } }, required: ['verdicts'] }

const CONTEXT = `Context: reading passages from Chinese 中考 (senior-high-school entrance exam) English papers, 2024-2026. They are written or adapted for 14-15-year-olds: short, simple sentences and a plain style are intended — never flag simplicity. Junior-high students will study and memorise them sentence by sentence, so the English must be COMPLETELY CORRECT. The texts were already proofread once; the corrections already applied are listed at the top of each file (including gaps in the exam that were filled with the answer sentences). This is the FINAL CHECK: find every remaining DEFINITE error — anything a careful English teacher or professional copy editor would mark wrong — and check that each applied correction is itself correct (report a bad correction with category 'bad-correction' and a fix). "The exam paper printed it that way" is NOT a reason to keep an error.
KEEP (never flag): British or American spelling and usage; legitimate journalistic style; informal but standard spoken English inside quotations; Chinese footnote glosses like "(范围)"; house style in the header. Do NOT report style preferences, optional commas, or rewrites of correct English — only definite errors.
Each review covers SEVERAL passage files; report each finding with its passage id ("pid").
Read-only: do NOT modify files. You may use web search to check a fact or the original source article.`

const LENSES = {
  A: `Your focus: go through EVERY sentence for spelling, punctuation (comma splices, run-ons, misplaced semicolons/colons, quotation marks, apostrophes, hyphens in compound modifiers), and grammar (agreement, including gerund and long subjects; tense and sequence of tenses; verb forms and patterns; articles and countability; pronoun reference and agreement; parallelism including not only/but also and either/or; comparatives; prepositions; dangling or misplaced modifiers; fragments).`,
  B: `Your focus: go through EVERY sentence for meaning: wrong word or collocation, wrong idiom, misused connectors (but/so/however/on the contrary…), statements contradicting the rest of the passage, impossible numbers/dates/facts, unclear or wrong pronoun reference that changes meaning; and examine each correction listed in the header — is it right, minimal, and does it fit the sentence? Also report any clear spelling/grammar/punctuation error you notice.`,
}
const key = f => `${f.pid}|${(f.current || '').toLowerCase().replace(/\s+/g, ' ').slice(0, 40)}`
const results = await pipeline(
  GROUPS,
  async g => {
    const files = g.map(id => `${DIR}/${id}.txt`).join(', ')
    const rs = await parallel(['A', 'B'].map(l => () => agent(`${CONTEXT}\n\nFiles: ${files} — read each whole file and check EVERY passage completely.\n\n${LENSES[l]}\n\nReport each definite error with its pid and a minimal fix. If a passage has none, say in notes which of its sentences you examined most closely.`, { label: `final${l}:G${g[0]}`, phase: 'Find', schema: REVIEW })))
    const seen = new Map()
    rs.forEach((r, i) => (r?.findings || []).forEach(f => { const k = key(f); if (!seen.has(k)) seen.set(k, { ...f, lens: ['A', 'B'][i] }) }))
    return { g, findings: [...seen.values()], failed: rs.filter(r => !r).length }
  },
  async r => {
    if (!r.findings.length) return { ...r, va: [], vb: [] }
    const list = r.findings.map((f, i) => `${i}: ${JSON.stringify({ pid: f.pid, loc: f.loc, current: f.current, proposed: f.proposed, category: f.category, reason: f.reason })}`).join('\n')
    const V = {
      acc: `Your lens: ACCURACY. Re-read each sentence in context yourself (in the file of its pid). Accept if the current text is definitely wrong and the fix is correct and minimal; amend if the error is real but the fix is imperfect; reject if the current text is correct, the issue is a style preference, or "current" does not match the text exactly.`,
      strict: `Your lens: STRICT EDITOR. Would a demanding English teacher or professional copy editor preparing texts for junior-high students to memorise mark this as an error? Accept (or amend) if yes. Do NOT reject because the exam printed it that way. Reject style preferences and changes to the meaning.`,
    }
    const [a, b] = await parallel(['acc', 'strict'].map(l => () => agent(`${CONTEXT}\n\nFiles: ${r.g.map(id => `${DIR}/${id}.txt`).join(', ')}\n\nProposed corrections (index: JSON):\n${list}\n\n${V[l]}\nReturn exactly one verdict per index with a short reason.`, { label: `verify-${l}:G${r.g[0]}`, phase: 'Verify', schema: VERDICTS })))
    return { ...r, va: a ? a.verdicts : null, vb: b ? b.verdicts : null }
  },
)
const per = []
for (const r of results.filter(Boolean)) {
  for (const id of r.g) {
    const idx = r.findings.map((f, i) => [f, i]).filter(([f]) => f.pid === id)
    const remap = v => v === null ? null : idx.map(([, i], j) => { const x = (v || []).find(y => y.index === i); return x ? { ...x, index: j } : null }).filter(Boolean)
    per.push({ id, findings: idx.map(([f]) => f), va: remap(r.va), vb: remap(r.vb), failed: r.failed })
  }
}
const IDS = GROUPS.flat()
const bad = per.filter(r => r.failed || r.va === null || r.vb === null).map(r => r.id)
if (bad.length) log(`incomplete: ${bad.join(', ')}`)
log(`done ${per.length}; findings ${per.reduce((s, r) => s + r.findings.length, 0)}`)
return { results: per, incomplete: bad, missing: IDS.filter(id => !per.find(r => r.id === id)) }
