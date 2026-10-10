export const meta = {
  name: 'strict-english-audit',
  description: 'Strict textbook-standard audit of the English source of 20 passages (grammar/usage + logic/facts/transcription), double-verified',
  phases: [
    { title: 'Find', detail: '2 independent English reviewers per passage: grammar/usage, logic/facts/transcription' },
    { title: 'Verify', detail: '2 independent verifiers per passage on merged findings + seeded candidates' },
  ],
}

const DIR = args.dir
const PIDS = args.pids
const SEEDS = args.seeds || {}

const FINDING = {
  type: 'object',
  properties: {
    sent: { type: 'integer', description: 'sentence number in [brackets]' },
    current: { type: 'string', description: 'exact erroneous substring of the EN sentence, copied character for character (curly quotes, dashes), long enough to be unique in that sentence' },
    proposed: { type: 'string', description: 'replacement substring (minimal fix)' },
    category: { type: 'string', enum: ['spelling', 'grammar', 'word-choice', 'punctuation', 'logic', 'fact', 'transcription'] },
    reason: { type: 'string' },
    zh_change: { type: 'string', description: 'if the ZH line must change after this fix, the FULL new ZH line; otherwise empty string' },
    severity: { type: 'string', enum: ['high', 'medium', 'low'] },
  },
  required: ['sent', 'current', 'proposed', 'category', 'reason', 'zh_change', 'severity'],
}
const REVIEW = { type: 'object', properties: { findings: { type: 'array', items: FINDING }, notes: { type: 'string' } }, required: ['findings', 'notes'] }
const VERDICTS = {
  type: 'object',
  properties: { verdicts: { type: 'array', items: { type: 'object', properties: {
    index: { type: 'integer' }, verdict: { type: 'string', enum: ['accept', 'reject', 'amend'] },
    amended_proposed: { type: 'string', description: 'for amend: the corrected replacement substring' },
    amended_zh: { type: 'string', description: 'for amend: corrected full ZH line if needed, else empty' },
    why: { type: 'string' } }, required: ['index', 'verdict', 'why'] } } },
  required: ['verdicts'],
}

const CONTEXT = `Context: English reading passages (C/D) from Chinese gaokao exam papers 2022–2026, turned into study materials for senior-high students: every sentence is shown on screen and read aloud by TTS, with a Chinese translation (ZH) and vocabulary glosses. The user has ordered: the English text must be COMPLETELY CORRECT — any grammar error, spelling error, wrong word, transcription error, or logically confused / self-contradictory / factually impossible statement must be corrected directly in the English (minimal fix that keeps the author's meaning). Students will memorise these sentences, so a sentence that a careful English teacher or professional copy editor would mark wrong must be fixed EVEN IF the original author or the exam paper wrote it that way ("it is authentic" or "it is the exam's own wording" is NOT a reason to keep an error). Some papers (header marked 回忆版) were reconstructed from memory and are more likely to contain transcription errors.
KEEP (never flag): British spelling and usage (colour, realise, whilst, in hospital, collective nouns with plural verbs, 1 January dates, punctuation outside quotes); legitimate journalistic style that is grammatical (ellipsis of repeated words, sentence fragments used deliberately as headings/lists, inversion, comma before a quoted attribution); informal but standard spoken English inside quotations (e.g. "gonna" would be fine in speech, "goes a little bit high" verbatim speech is acceptable); numerals at the start of a sentence; the Chinese footnotes in parentheses like "(性别)" (exam footnotes, stripped automatically). Do not rewrite for style.
Read-only: do NOT modify any files. You may use web search to check a source text or a fact.`

const LENSES = {
  grammar: `Your lens: GRAMMAR AND USAGE, strictly, sentence by sentence, at the standard of a demanding English teacher marking an essay: subject–verb agreement; tense and aspect (e.g. "in the past year" / "since" / "so far" normally require the present perfect; "wish" about the past requires the past perfect); verb patterns (worry about, consider whether); countable vs uncountable nouns and articles ("an AI software", missing "the" before institution names like "the Salk Institute"); determiners and pronoun agreement / person shift within a sentence ("your goal … our own destiny"); faulty parallelism ("on my behalf and all womankind"); dangling or misattached modifiers that make the grammatical subject wrong ("While earning my Ph.D., the issue started to bother me"); sentence fragments that are not deliberate ("Because every time we surface …" standing alone); comparatives/superlatives ("among the highest rate"); idioms in the wrong form ("for better" instead of "for the better"); prepositions; word form; non-existent words; spelling.`,
  logic: `Your lens: LOGIC, FACTS AND TRANSCRIPTION: statements that contradict another sentence of the same passage; wrong or impossible numbers/units/conversions (e.g. 1/20000 inch ≠ 1 micrometer); statements that are logically confused given the passage (e.g. saying all reviews were written by people given hotel information when the passage distinguishes real and fake reviews); misused technical terms or idioms that say something different from what is meant (e.g. "zero-sum game" for a lose-lose choice); wrong connectors (but/so/because/therefore) where the logical relation is different; words that make no sense in context and look like mis-hearing or mis-typing in a recalled paper; names inconsistent within the passage. Where possible, use web search to find the original source article and compare. Also report any clear grammar/spelling error you notice.`,
}

function findPrompt(pid, lens) {
  return `${CONTEXT}

File: ${DIR}/${pid}.txt — read the WHOLE file. Each sentence is shown as [n] EN: … / ZH: … followed by vocabulary lines.

${LENSES[lens]}

Check EVERY EN sentence. Report each real error with the minimal fix ("current" = exact substring to replace, "proposed" = replacement). If the ZH translation must change because of your fix, give the full new ZH line in zh_change (keep the rest of the existing ZH wording). If you find nothing, return an empty list, and in notes list the sentences you looked at most closely and why you kept them.`
}

function verifyPrompt(pid, findings, lens) {
  const L = lens === 'acc'
    ? `Your lens: ACCURACY. For each proposed fix, re-read the EN sentence and its context yourself. Accept if the current English is genuinely wrong by the standard above and the replacement is correct, minimal and keeps the meaning. If the error is real but the replacement is imperfect (not minimal, introduces a new problem, wrong ZH), "amend" with a better replacement substring (and ZH if needed). Reject if the current English is actually correct (including British usage or legitimate style).`
    : `Your lens: STRICT TEACHER. For each proposed fix decide: would a demanding English teacher or a professional copy editor preparing these texts for students to memorise mark the current wording as an error? If yes, accept (or amend if the fix is not the best minimal one). Do NOT reject merely because the original author/exam wrote it that way — that is explicitly not a reason to keep an error. Reject only if the current English is correct, the change is pure style, it would change the author's meaning, or "current" does not match the EN sentence exactly.`
  return `${CONTEXT}

File: ${DIR}/${pid}.txt

Proposed corrections to the English (index: JSON):
${findings.map((f, i) => `${i}: ${JSON.stringify(f)}`).join('\n')}

${L}
Return exactly one verdict per index with a short reason.`
}

const key = f => `${f.sent}|${(f.current || '').toLowerCase().replace(/\s+/g, ' ').slice(0, 30)}`

const results = await pipeline(
  PIDS,
  async pid => {
    const lenses = ['grammar', 'logic']
    const rs = await parallel(lenses.map(lens => () =>
      agent(findPrompt(pid, lens), { label: `${lens}:${pid}`, phase: 'Find', schema: REVIEW })))
    const seen = new Map()
    rs.forEach((r, i) => (r?.findings || []).forEach(f => {
      const k = key(f)
      if (!seen.has(k)) seen.set(k, { ...f, lens: lenses[i] })
    }))
    for (const s of (SEEDS[pid] || [])) {
      const k = key(s)
      if (!seen.has(k)) seen.set(k, { ...s, lens: 'seed' })
    }
    return { pid, findings: [...seen.values()], notes: rs.map(r => r?.notes || '') }
  },
  async r => {
    if (!r.findings.length) return { pid: r.pid, kept: [], dropped: [], notes: r.notes }
    const [a, b] = await parallel([
      () => agent(verifyPrompt(r.pid, r.findings, 'acc'), { label: `verify-acc:${r.pid}`, phase: 'Verify', schema: VERDICTS }),
      () => agent(verifyPrompt(r.pid, r.findings, 'strict'), { label: `verify-strict:${r.pid}`, phase: 'Verify', schema: VERDICTS }),
    ])
    const va = new Map((a?.verdicts || []).map(v => [v.index, v]))
    const vb = new Map((b?.verdicts || []).map(v => [v.index, v]))
    const kept = [], dropped = []
    r.findings.forEach((f, i) => {
      const x = va.get(i), y = vb.get(i)
      const g = { ...f, pid: r.pid, votes: [x?.verdict, y?.verdict], why: [x?.why, y?.why],
        amended: [x?.amended_proposed || '', y?.amended_proposed || ''], amended_zh: [x?.amended_zh || '', y?.amended_zh || ''] }
      if (!x || !y || x.verdict === 'reject' || y.verdict === 'reject') dropped.push(g)
      else kept.push(g)
    })
    return { pid: r.pid, kept, dropped, notes: r.notes }
  },
)
const ok = results.filter(Boolean)
const kept = ok.flatMap(r => r.kept), dropped = ok.flatMap(r => r.dropped)
log(`kept ${kept.length}, dropped ${dropped.length}`)
return { kept, dropped, notes: ok.map(r => ({ pid: r.pid, notes: r.notes })) }
