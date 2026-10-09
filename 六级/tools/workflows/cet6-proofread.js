export const meta = {
  name: 'cet6-proofread',
  description: 'Strict proofreading of 58 CET-6 Section C passages (+2 canaries): fidelity vs page images, mechanics, grammar, logic; each finding double-verified',
  phases: [
    { title: 'Find', detail: '4 independent reviewers per passage: fidelity to printed page, spelling/punctuation/typography, grammar/usage, word choice/logic/facts' },
    { title: 'Verify', detail: '2 independent verifiers per passage on merged findings: accuracy (checks page image), strict editor' },
  ],
}

const DIR = args.dir
const IDS = args.ids

const FINDING = {
  type: 'object',
  properties: {
    loc: { type: 'string', description: 'sentence label like [3.2], or ¶3 for paragraph-level issues' },
    current: { type: 'string', description: 'exact substring of the CURRENT text, copied character for character (curly quotes ’ “ ”, em dash —), long enough to be unique in the whole passage. For a paragraph-break issue, the first few words of the sentence where the break is wrong/missing.' },
    proposed: { type: 'string', description: 'replacement for that substring (minimal fix). For a paragraph-break issue, describe e.g. "start a new paragraph before this sentence".' },
    category: { type: 'string', enum: ['transcription', 'paragraphing', 'spelling', 'punctuation', 'typography', 'grammar', 'word-choice', 'logic', 'fact'] },
    printed: { type: 'string', description: 'what the printed exam page shows at this spot (copy it), or "not checked"' },
    reason: { type: 'string' },
    severity: { type: 'string', enum: ['high', 'medium', 'low'] },
  },
  required: ['loc', 'current', 'proposed', 'category', 'printed', 'reason', 'severity'],
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

const CONTEXT = `Context: reading passages (Section C, "careful reading") from China's College English Test Band 6 (CET-6) papers, December 2021 – June 2026. Chinese university students will study, memorise and recite these texts, so the English must be COMPLETELY CORRECT. The text was extracted from the exam PDFs (for the December 2021 and June 2022 papers it was re-typed by hand from scans). Two kinds of error must be found:
(A) TRANSCRIPTION errors — the text differs from the printed exam page: missing/extra/changed words, letters, numbers, names, punctuation, capitalisation, hyphenation, a lost or extra paragraph break, a wrong Chinese footnote character.
(B) Errors IN THE PRINTED PAPER ITSELF — spelling, grammar, punctuation, wrong word, wrong idiom, logical contradiction, factual impossibility. These must be corrected too: a sentence that a careful English teacher or professional copy editor would mark wrong must be fixed EVEN IF the exam paper printed it that way ("it is the exam's original wording" is NOT a reason to keep an error). Use a minimal fix that keeps the author's meaning.
KEEP (never flag): British spelling and usage (realise, whilst, in hospital, Dr without a full stop, collective nouns with plural verbs, punctuation outside quotes); American spelling; legitimate journalistic style that is grammatical (deliberate fragments, inversion, ellipsis); informal but standard spoken English inside quotations; the Chinese footnote glosses in parentheses like "(耻辱)" (they belong to the exam); the house style listed in the file header (版式约定), and items the header lists as already decided (已决定不改) unless you have a new, definite reason. Do NOT rewrite for style or "improve" correct English — only report what is actually wrong. Do not report differences already listed in the file header as corrected on purpose (已经做过的订正) — but DO report if such a correction is itself wrong.
Read-only: do NOT modify any files. Use the Read tool to view PNG page images. You may use web search to find the original source article to check a suspected error.`

const LENSES = {
  fidelity: `Your lens: FIDELITY TO THE PRINTED PAGE. Open every page image listed in the file header with the Read tool (zoom is not available, so read carefully; the passage may continue onto the second image — ignore the questions and other passages). Compare the text with the print WORD BY WORD, sentence by sentence, including every number, name, punctuation mark, capital letter, hyphen, apostrophe, and the Chinese footnote characters. Check every paragraph break: in the print a new paragraph starts with an indented first line; make sure the ¶ divisions match exactly (no merged or split paragraphs). Check that no sentence or phrase is missing or duplicated. Report EVERY difference (category transcription or paragraphing) with "printed" showing exactly what the page shows. If you also notice an obvious error in the printed text itself, report it too (with the right category). In notes, state how many paragraphs the print has and whether you compared all of them.`,
  mechanics: `Your lens: SPELLING, PUNCTUATION AND TYPOGRAPHY, character by character: misspelled or non-existent words; wrong homophones (their/there, its/it's, affect/effect, lose/loose, principal/principle); missing or wrong apostrophes; capitalisation (sentence starts, proper nouns, titles); comma errors that a copy editor would definitely correct (comma splices joining two independent clauses, a comma between subject and verb, missing comma that changes or garbles the meaning, unpaired commas around a non-restrictive element); question mark vs full stop; quotation marks (pairing, placement, wrong direction, missing closing quote); parentheses pairing; hyphens vs dashes; missing hyphen in a compound adjective before a noun (e.g. "long term goals" → "long-term goals") and wrongly hyphenated words; spacing problems; inconsistent spelling of the same name or word within the passage; number formatting. Check EVERY sentence. You may glance at the page image to see whether an error is in the print, but your job is the correctness of the CURRENT text.`,
  grammar: `Your lens: GRAMMAR AND USAGE, strictly, sentence by sentence, at the standard of a demanding English teacher: subject–verb agreement (watch long subjects: "much of the music that … uses"); tense and aspect consistency; verb patterns and complementation; countable vs uncountable nouns and articles (missing/extra a/an/the); determiners and pronoun agreement/reference; person shifts; faulty parallelism; dangling or misattached modifiers; non-deliberate sentence fragments and run-ons; comparatives and superlatives ("most major", "more better"); idioms in the wrong form ("come to no surprise", "in the least bit"); prepositions; word form (adjective vs adverb, noun vs verb); relative pronouns; double negatives; redundancy that is ungrammatical. Check EVERY sentence. Report only real errors, not style preferences.`,
  logic: `Your lens: WORD CHOICE, LOGIC AND FACTS: words that are wrong for the meaning (wrong collocation, malapropism, false friend, misused term or idiom); statements that contradict another sentence of the same passage or the passage's own argument (e.g. "few" vs "many" reversing the point); wrong connectors (but/so/because/therefore/however/even so) where the logical relation is different; impossible or inconsistent numbers, dates, ages, timelines, percentages, units; names inconsistent within the passage; words that make no sense in context and look like a typing error. Where helpful, use web search to find the original source article and compare (the exam often adapts its source; only an adaptation that introduced an ERROR counts). Also report any clear grammar/spelling/punctuation error you notice.`,
}

function findPrompt(id, lens) {
  return `${CONTEXT}

File: ${DIR}/${id}.txt — read the WHOLE file, including the header lines.

${LENSES[lens]}

Report each real error with the minimal fix ("current" = exact substring of the current text, "proposed" = replacement). If you find nothing, return an empty list, and in notes list the sentences you looked at most closely and why you kept them.`
}

function verifyPrompt(id, findings, lens) {
  const L = lens === 'acc'
    ? `Your lens: ACCURACY. For each proposed fix: read the sentence and its context yourself; for transcription/paragraphing findings (and whenever a finding depends on what the exam printed) OPEN THE PAGE IMAGE(S) and check the print yourself, and record what it shows in "printed". Accept if the current text is genuinely wrong (differs from the print, or is an error by the standard above) and the replacement is correct, minimal and keeps the meaning. If the error is real but the replacement is imperfect (not minimal, introduces a new problem, does not match the print), "amend" with a better replacement. Reject if the current text is actually correct and matches the print, or the finding is a style preference, British usage, house style, or a difference already corrected on purpose.`
    : `Your lens: STRICT EDITOR. For each proposed fix decide: would a demanding English teacher or professional copy editor preparing these texts for students to memorise mark the current wording as an error (or is it a transcription difference from the printed page)? If yes, accept (or amend if the fix is not the best minimal one). Do NOT reject merely because the exam paper printed it that way — that is explicitly not a reason to keep an error. Reject only if the current text is correct, the change is pure style, it would change the author's meaning, or "current" does not match the text exactly.`
  return `${CONTEXT}

File: ${DIR}/${id}.txt

Proposed corrections (index: JSON):
${findings.map((f, i) => `${i}: ${JSON.stringify(f)}`).join('\n')}

${L}
Return exactly one verdict per index with a short reason.`
}

const key = f => `${(f.current || '').toLowerCase().replace(/\s+/g, ' ').slice(0, 40)}`
const LENS_NAMES = ['fidelity', 'mechanics', 'grammar', 'logic']

const results = await pipeline(
  IDS,
  async id => {
    const rs = await parallel(LENS_NAMES.map(lens => () =>
      agent(findPrompt(id, lens), { label: `${lens}:${id}`, phase: 'Find', schema: REVIEW })))
    const seen = new Map()
    rs.forEach((r, i) => (r?.findings || []).forEach(f => {
      const k = key(f)
      if (!seen.has(k)) seen.set(k, { ...f, lens: [LENS_NAMES[i]] })
      else if (!seen.get(k).lens.includes(LENS_NAMES[i])) seen.get(k).lens.push(LENS_NAMES[i])
    }))
    return { id, findings: [...seen.values()], notes: Object.fromEntries(rs.map((r, i) => [LENS_NAMES[i], r ? r.notes : 'AGENT FAILED'])) }
  },
  async r => {
    if (!r.findings.length) return { id: r.id, kept: [], dropped: [], notes: r.notes }
    const [a, b] = await parallel([
      () => agent(verifyPrompt(r.id, r.findings, 'acc'), { label: `verify-acc:${r.id}`, phase: 'Verify', schema: VERDICTS }),
      () => agent(verifyPrompt(r.id, r.findings, 'strict'), { label: `verify-strict:${r.id}`, phase: 'Verify', schema: VERDICTS }),
    ])
    const va = new Map((a?.verdicts || []).map(v => [v.index, v]))
    const vb = new Map((b?.verdicts || []).map(v => [v.index, v]))
    const kept = [], dropped = []
    r.findings.forEach((f, i) => {
      const x = va.get(i), y = vb.get(i)
      const g = { ...f, id: r.id, votes: [x?.verdict, y?.verdict], why: [x?.why, y?.why], printed_v: x?.printed || '',
        amended: [x?.amended_proposed || '', y?.amended_proposed || ''] }
      if (!x || !y || x.verdict === 'reject' || y.verdict === 'reject') dropped.push(g)
      else kept.push(g)
    })
    return { id: r.id, kept, dropped, notes: r.notes }
  },
)
const ok = results.filter(Boolean)
const failed = IDS.filter(id => !ok.find(r => r.id === id))
if (failed.length) log(`FAILED items: ${failed.join(', ')}`)
const kept = ok.flatMap(r => r.kept), dropped = ok.flatMap(r => r.dropped)
log(`kept ${kept.length}, dropped ${dropped.length}`)
return { kept, dropped, failed, notes: ok.map(r => ({ id: r.id, notes: r.notes })) }
