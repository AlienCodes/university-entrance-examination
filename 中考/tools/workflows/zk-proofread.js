export const meta = {
  name: 'zk-proofread',
  description: 'Strict proofreading of 中考 reading passages in groups (+canaries): fidelity vs original Word pages, mechanics, grammar, logic; each finding double-verified',
  phases: [
    { title: 'Find', detail: '4 independent reviewers per group of passages: fidelity to original, spelling/punctuation/typography, grammar/usage, word choice/logic/facts' },
    { title: 'Verify', detail: '2 independent verifiers per group on merged findings: accuracy (checks original), strict editor' },
  ],
}
// args: {dir, groups: [[id, ...], ...]}
const DIR = args.dir
const GROUPS = args.groups

const FINDING = {
  type: 'object',
  properties: {
    pid: { type: 'string', description: 'passage file id, e.g. z07' },
    loc: { type: 'string', description: 'sentence label like [3.2], or ¶3 for paragraph-level issues' },
    current: { type: 'string', description: 'exact substring of the CURRENT text, copied character for character (curly quotes ’ “ ”, em dash —), long enough to be unique in the whole passage. For a paragraph-break issue, the first few words of the sentence where the break is wrong/missing.' },
    proposed: { type: 'string', description: 'replacement for that substring (minimal fix). For a paragraph-break issue, describe e.g. "start a new paragraph before this sentence".' },
    category: { type: 'string', enum: ['transcription', 'paragraphing', 'spelling', 'punctuation', 'typography', 'grammar', 'word-choice', 'logic', 'fact'] },
    printed: { type: 'string', description: 'what the printed exam page shows at this spot (copy it), or "not checked"' },
    reason: { type: 'string' },
    severity: { type: 'string', enum: ['high', 'medium', 'low'] },
  },
  required: ['pid', 'loc', 'current', 'proposed', 'category', 'printed', 'reason', 'severity'],
}
const REVIEW = { type: 'object', properties: { findings: { type: 'array', items: FINDING }, notes: { type: 'string' } }, required: ['findings', 'notes'] }
const VERDICTS = {
  type: 'object',
  properties: { verdicts: { type: 'array', items: { type: 'object', properties: {
    index: { type: 'integer' }, verdict: { type: 'string', enum: ['accept', 'reject', 'amend'] },
    amended_proposed: { type: 'string', description: 'for amend: the corrected replacement substring' },
    printed: { type: 'string', description: 'what the printed page shows at this spot, if you checked' },
    why: { type: 'string' } }, required: ['index', 'verdict', 'why'] } } },
  required: ['verdicts'],
}

const CONTEXT = `Context: reading passages from Chinese 中考 (senior-high-school entrance exam; students aged 14-15) English papers, 2024-2026, from many provinces. Junior-high students will study these texts sentence by sentence in vocabulary videos and memorise them, so the English must be COMPLETELY CORRECT. The text was extracted directly from the Word (.docx) files of the papers (digital text, no OCR), so letter-level transcription errors are rare; the main risks are: passage boundaries (a paragraph missing at the start/end, question text mixed in), paragraph breaks, removed markers (①② paragraph numbers, a footnote asterisk), filled gaps (sentence-insertion gaps ▲/★ and a 7-choose-5 passage were completed with the answer sentences — check that each fill is the right sentence, grammatical and logical in context), and errors in the paper itself. Each file header lists page images rendered from the Word file and a full-text dump of the whole paper (passage + questions, sometimes answers and explanations that quote the passage). Two kinds of error must be found:
(A) TRANSCRIPTION errors — the text differs from the original: missing/extra/changed words, letters, numbers, names, punctuation, capitalisation, hyphenation, a lost or extra paragraph break, a wrong Chinese footnote character.
(B) Errors IN THE PAPER ITSELF — spelling, grammar, punctuation, wrong word, wrong idiom, logical contradiction, factual impossibility, wrong tense. These must be corrected too: a sentence that a careful English teacher or professional copy editor would mark wrong must be fixed EVEN IF the exam paper printed it that way ("it is the exam's original wording" is NOT a reason to keep an error). Use a minimal fix that keeps the meaning.
中考 passages are written or adapted for 14-15-year-olds: short, simple sentences and a plain style are intended — never flag simplicity or ask for more sophisticated wording. But adaptation errors (grammar, wrong word, tense, articles, factual slips) are common and must be fixed.
KEEP (never flag): British spelling and usage; American spelling; legitimate journalistic style that is grammatical; informal but standard spoken English inside quotations; the Chinese footnote glosses in parentheses like "(范围)" (they belong to the exam); the house style listed in the file header (版式约定) and the programmatic normalisations listed there; items the header lists as already decided (已决定不改) unless you have a new, definite reason. Do NOT rewrite for style or "improve" correct English — only report what is actually wrong. Do not report differences already listed in the file header as corrected on purpose (已经做过的订正) — but DO report if such a correction is itself wrong or was not applied as described.
Read-only: do NOT modify any files. Use the Read tool to view PNG page images and text files. You may use web search to find the original source article to check a suspected error.`

const LENSES = {
  fidelity: `Your lens: FIDELITY TO THE PRINTED PAGE. Open every page image listed in each file header with the Read tool (the passage may continue onto the next image — ignore the questions and other passages) AND the full-text dump of the paper named in the header. Compare the text with the original WORD BY WORD, sentence by sentence, including every number, name, punctuation mark, capital letter, hyphen, apostrophe, and the Chinese footnote characters. Check every paragraph break: ¶ count and breaks must equal the original paragraphs exactly (no merged or split paragraphs), and the passage must start and end exactly where the original passage does (nothing missing, no question text mixed in). For gaps that were filled (listed in the header as already made corrections), check that the CURRENT text contains exactly the sentence the header says and that it fits the context. Check that no sentence or phrase is missing or duplicated. Report EVERY difference (category transcription or paragraphing) with "printed" showing exactly what the page shows. If you also notice an obvious error in the printed text itself, report it too (with the right category). In notes, for EACH passage state how many paragraphs the original has and whether you compared all of them.`,
  mechanics: `Your lens: SPELLING, PUNCTUATION AND TYPOGRAPHY, character by character: misspelled or non-existent words; wrong homophones (their/there, its/it's, affect/effect, lose/loose, principal/principle); missing or wrong apostrophes; capitalisation (sentence starts, proper nouns, titles); comma errors that a copy editor would definitely correct (comma splices joining two independent clauses, a comma between subject and verb, missing comma that changes or garbles the meaning, unpaired commas around a non-restrictive element); question mark vs full stop; quotation marks (pairing, placement, wrong direction, missing closing quote); parentheses pairing; hyphens vs dashes; missing hyphen in a compound adjective before a noun (e.g. "long term goals" → "long-term goals") and wrongly hyphenated words; spacing problems; inconsistent spelling of the same name or word within the passage; number formatting. Check EVERY sentence. You may glance at the page image to see whether an error is in the print, but your job is the correctness of the CURRENT text.`,
  grammar: `Your lens: GRAMMAR AND USAGE, strictly, sentence by sentence, at the standard of a demanding English teacher: subject–verb agreement (watch long subjects: "much of the music that … uses"); tense and aspect consistency; verb patterns and complementation; countable vs uncountable nouns and articles (missing/extra a/an/the); determiners and pronoun agreement/reference; person shifts; faulty parallelism; dangling or misattached modifiers; non-deliberate sentence fragments and run-ons; comparatives and superlatives ("most major", "more better"); idioms in the wrong form ("come to no surprise", "in the least bit"); prepositions; word form (adjective vs adverb, noun vs verb); relative pronouns; double negatives; redundancy that is ungrammatical. Check EVERY sentence. Report only real errors, not style preferences.`,
  logic: `Your lens: WORD CHOICE, LOGIC AND FACTS: words that are wrong for the meaning (wrong collocation, malapropism, false friend, misused term or idiom); statements that contradict another sentence of the same passage or the passage's own argument (e.g. "few" vs "many" reversing the point); wrong connectors (but/so/because/therefore/however/even so) where the logical relation is different; impossible or inconsistent numbers, dates, ages, timelines, percentages, units; names inconsistent within the passage; words that make no sense in context and look like a typing error. Where helpful, use web search to find the original source article and compare (the exam often adapts its source; only an adaptation that introduced an ERROR counts). Also report any clear grammar/spelling/punctuation error you notice.`,
}

function findPrompt(g, lens) {
  return `${CONTEXT}

Files (one passage each; review EVERY one completely): ${g.map(id => `${DIR}/${id}.txt`).join(', ')} — read each WHOLE file, including the header lines.

${LENSES[lens]}

Report each real error with the passage id ("pid"), the minimal fix ("current" = exact substring of that passage's current text, "proposed" = replacement). If you find nothing in a passage, say so in notes, listing the sentences you looked at most closely and why you kept them.`
}
function verifyPrompt(g, findings, lens) {
  const L = lens === 'acc'
    ? `Your lens: ACCURACY. For each proposed fix: read the sentence and its context yourself in the passage file named by its pid; for transcription/paragraphing findings (and whenever a finding depends on what the original says) OPEN THE PAGE IMAGE(S) or the full-text dump and check the original yourself, and record what it shows in "printed". Accept if the current text is genuinely wrong (differs from the original, or is an error by the standard above) and the replacement is correct, minimal and keeps the meaning. If the error is real but the replacement is not the best minimal fix, use amend with amended_proposed. Reject if the current text is correct, or the claim is false, or it is only a style preference.`
    : `Your lens: STRICT EDITOR. For each proposed fix decide: would a demanding English teacher or professional copy editor preparing these texts for junior-high students to memorise mark the current wording as an error (or is it a transcription difference from the original)? If yes, accept (or amend if the fix is not the best minimal one). Do NOT reject merely because the exam paper printed it that way — that is explicitly not a reason to keep an error. Reject only if the current text is correct, the claim is false, or it is a style preference.`
  return `${CONTEXT}

Files: ${g.map(id => `${DIR}/${id}.txt`).join(', ')}

Proposed corrections (index: JSON):
${findings.map((f, i) => `${i}: ${JSON.stringify(f)}`).join('\n')}

${L}
Return exactly one verdict per index with a short reason.`
}

const key = f => `${f.pid}|${(f.current || '').toLowerCase().replace(/\s+/g, ' ').slice(0, 40)}`
const LENS_NAMES = ['fidelity', 'mechanics', 'grammar', 'logic']

const results = await pipeline(
  GROUPS,
  async (g, _, gi) => {
    const rs = await parallel(LENS_NAMES.map(lens => () =>
      agent(findPrompt(g, lens), { label: `${lens}:G${g[0]}`, phase: 'Find', schema: REVIEW })))
    const seen = new Map()
    rs.forEach((r, i) => (r?.findings || []).forEach(f => {
      const k = key(f)
      if (!seen.has(k)) seen.set(k, { ...f, lens: [LENS_NAMES[i]] })
      else if (!seen.get(k).lens.includes(LENS_NAMES[i])) seen.get(k).lens.push(LENS_NAMES[i])
    }))
    return { g, findings: [...seen.values()], notes: Object.fromEntries(rs.map((r, i) => [LENS_NAMES[i], r ? r.notes : 'AGENT FAILED'])), failed: rs.filter(r => !r).length }
  },
  async r => {
    if (!r.findings.length) return { g: r.g, kept: [], dropped: [], notes: r.notes, failed: r.failed }
    const [a, b] = await parallel([
      () => agent(verifyPrompt(r.g, r.findings, 'acc'), { label: `verify-acc:G${r.g[0]}`, phase: 'Verify', schema: VERDICTS }),
      () => agent(verifyPrompt(r.g, r.findings, 'strict'), { label: `verify-strict:G${r.g[0]}`, phase: 'Verify', schema: VERDICTS }),
    ])
    const va = new Map((a?.verdicts || []).map(v => [v.index, v]))
    const vb = new Map((b?.verdicts || []).map(v => [v.index, v]))
    const kept = [], dropped = []
    r.findings.forEach((f, i) => {
      const x = va.get(i), y = vb.get(i)
      const o = { ...f, votes: [x?.verdict, y?.verdict], why: [x?.why, y?.why], printed_v: x?.printed || '',
        amended: [x?.amended_proposed || '', y?.amended_proposed || ''] }
      if (!x || !y || x.verdict === 'reject' || y.verdict === 'reject') dropped.push(o)
      else kept.push(o)
    })
    return { g: r.g, kept, dropped, notes: r.notes, failed: r.failed + (a ? 0 : 1) + (b ? 0 : 1) }
  },
)
const ok = results.filter(Boolean)
const failed = GROUPS.filter(g => !ok.find(r => r.g[0] === g[0])).map(g => g.join(','))
const agentFail = ok.filter(r => r.failed).map(r => r.g.join(','))
if (failed.length || agentFail.length) log(`FAILED groups: ${failed.join(' | ')}; groups with failed agents: ${agentFail.join(' | ')}`)
const kept = ok.flatMap(r => r.kept), dropped = ok.flatMap(r => r.dropped)
log(`kept ${kept.length}, dropped ${dropped.length}`)
return { kept, dropped, failed, agentFail, notes: ok.map(r => ({ g: r.g, notes: r.notes })) }
