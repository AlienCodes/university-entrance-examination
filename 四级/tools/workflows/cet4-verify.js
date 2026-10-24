export const meta = {
  name: 'cet4-proofread-v3',
  description: 'CET-4 Section C proofreading, 60 passages: reuse round-1 finder results, run finders for 2 new passages, double-verify every finding (canaries included)',
  phases: [
    { title: 'Find', detail: '4 reviewers for passages without round-1 findings' },
    { title: 'Verify', detail: '2 independent verifiers per passage: accuracy (checks page image), strict editor' },
  ],
}

const ITEMS = args.ids.map(id => ({
  id,
  file: args.canary[id] ? `${args.rv1}/${args.canary[id]}.txt` : `${args.rv2}/${id}.txt`,
  seedFile: args.noSeeds.includes(id) ? null : `${args.seeds}/${id}.json`,
}))

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

const CONTEXT = `Context: reading passages (Section C, "careful reading") from China's College English Test Band 4 (CET-4) papers, 2021–2026. Chinese university students will study, memorise and recite these texts, so the English must be COMPLETELY CORRECT. The text was extracted from the exam PDFs (for 2021 papers it was re-typed by hand from scans). Two kinds of error must be found:
(A) TRANSCRIPTION errors — the text differs from the printed exam page: missing/extra/changed words, letters, numbers, names, punctuation, capitalisation, hyphenation, a lost or extra paragraph break, a wrong Chinese footnote character.
(B) Errors IN THE PRINTED PAPER ITSELF — spelling, grammar, punctuation, wrong word, wrong idiom, logical contradiction, factual impossibility. These must be corrected too: a sentence that a careful English teacher or professional copy editor would mark wrong must be fixed EVEN IF the exam paper printed it that way ("it is the exam's original wording" is NOT a reason to keep an error). Use a minimal fix that keeps the author's meaning.
KEEP (never flag): British spelling and usage (realise, whilst, in hospital, Dr without a full stop, collective nouns with plural verbs, punctuation outside quotes); American spelling; legitimate journalistic style that is grammatical (deliberate fragments, inversion, ellipsis); informal but standard spoken English inside quotations; the Chinese footnote glosses in parentheses like "(耻辱)" (they belong to the exam); the house style listed in the file header. Do NOT rewrite for style or "improve" correct English — only report what is actually wrong. Do not report differences already listed in the file header as corrected on purpose.
Read-only: do NOT modify any files. Use the Read tool to view PNG page images. You may use web search to find the original source article to check a suspected error.`

const LENSES = {
  fidelity: `Your lens: FIDELITY TO THE PRINTED PAGE. Open every page image listed in the file header with the Read tool (the passage may start at the bottom of one image and continue onto the next — ignore the questions and other passages). Compare the text with the print WORD BY WORD, sentence by sentence, including every number, name, punctuation mark, capital letter, hyphen, apostrophe, and the Chinese footnote characters. Check every paragraph break: in this print a new paragraph may be marked by an indented first line OR by extra vertical space between paragraphs; make sure the ¶ divisions match exactly (no merged or split paragraphs). Check that no sentence or phrase is missing or duplicated. Report EVERY difference (category transcription or paragraphing) with "printed" showing exactly what the page shows. If you also notice an obvious error in the printed text itself, report it too (with the right category). In notes, state how many paragraphs the print has and whether you compared all of them.`,
  mechanics: `Your lens: SPELLING, PUNCTUATION AND TYPOGRAPHY, character by character: misspelled or non-existent words; wrong homophones (their/there, its/it's, affect/effect, lose/loose, principal/principle); missing or wrong apostrophes; capitalisation (sentence starts, proper nouns, titles); comma errors that a copy editor would definitely correct (comma splices joining two independent clauses, a comma between subject and verb, missing comma that changes or garbles the meaning, unpaired commas around a non-restrictive element); question mark vs full stop; quotation marks (pairing, placement, wrong direction, missing closing quote); parentheses pairing; hyphens vs dashes; missing hyphen in a compound adjective before a noun and wrongly hyphenated words; spacing problems; inconsistent spelling of the same name or word within the passage; number formatting. Check EVERY sentence.`,
  grammar: `Your lens: GRAMMAR AND USAGE, strictly, sentence by sentence, at the standard of a demanding English teacher: subject–verb agreement (watch long subjects); tense and aspect consistency; verb patterns and complementation; countable vs uncountable nouns and articles (missing/extra a/an/the); determiners and pronoun agreement/reference; person shifts; faulty parallelism; dangling or misattached modifiers; non-deliberate sentence fragments and run-ons; comparatives and superlatives; idioms in the wrong form; prepositions; word form; relative pronouns; double negatives. Check EVERY sentence. Report only real errors, not style preferences.`,
  logic: `Your lens: WORD CHOICE, LOGIC AND FACTS: words that are wrong for the meaning (wrong collocation, malapropism, misused term or idiom); statements that contradict another sentence of the same passage or the passage's own argument; wrong connectors (but/so/because/therefore/however) where the logical relation is different; impossible or inconsistent numbers, dates, ages, timelines, percentages, units; names inconsistent within the passage; tense that contradicts the facts (e.g. "never used" for a current practice); words that make no sense in context. Where helpful, use web search to find the original source article and compare (the exam often adapts its source; only an adaptation that introduced an ERROR counts). Also report any clear grammar/spelling/punctuation error you notice.`,
}

function findPrompt(file, lens) {
  return `${CONTEXT}

File: ${file} — read the WHOLE file, including the header lines.

${LENSES[lens]}

Report each real error with the minimal fix ("current" = exact substring of the current text, "proposed" = replacement). If you find nothing, return an empty list, and in notes list the sentences you looked at most closely and why you kept them.`
}

function verifyPrompt(file, findings, lens, seedFile) {
  const L = lens === 'acc'
    ? `Your lens: ACCURACY. For each proposed fix: read the sentence and its context yourself; for transcription/paragraphing findings (and whenever a finding depends on what the exam printed) OPEN THE PAGE IMAGE(S) listed in the file header and check the print yourself, and record what it shows in "printed". Accept if the current text is genuinely wrong (differs from the print, or is an error by the standard above) and the replacement is correct, minimal and keeps the meaning. If the error is real but the replacement is imperfect (not minimal, introduces a new problem, does not match the print, or better fixed another way), "amend" with a better replacement. Reject if the current text is actually correct and matches the print, or the finding is a style preference, British usage, house style, or a difference already corrected on purpose.`
    : `Your lens: STRICT EDITOR. For each proposed fix decide: would a demanding English teacher or professional copy editor preparing these texts for students to memorise mark the current wording as an error (or is it a transcription difference from the printed page)? If yes, accept (or amend if the fix is not the best minimal one). Do NOT reject merely because the exam paper printed it that way — that is explicitly not a reason to keep an error. Reject only if the current text is correct, the change is pure style, it would change the author's meaning, or "current" does not match the text exactly.`
  return `${CONTEXT}

File: ${file}

${seedFile ? `Proposed corrections: read the JSON array in ${seedFile} with the Read tool — the index of each correction is its position in the array, starting at 0. Several reviewers may have proposed overlapping fixes for the same spot; judge each on its own merits.` : `Proposed corrections (index: JSON). Several reviewers may have proposed overlapping fixes for the same spot; judge each on its own merits:
${findings.map((f, i) => `${i}: ${JSON.stringify({ loc: f.loc, current: f.current, proposed: f.proposed, category: f.category, printed: f.printed, reason: f.reason })}`).join('\n')}`}

${L}
Return exactly one verdict per index with a short reason.`
}

const key = f => `${(f.current || '').toLowerCase().replace(/\s+/g, ' ').slice(0, 40)}`
const LENS_NAMES = ['fidelity', 'mechanics', 'grammar', 'logic']

const results = await pipeline(
  ITEMS,
  async it => {
    if (it.seedFile) return { id: it.id, file: it.file, seedFile: it.seedFile, findings: args.empty.includes(it.id) ? [] : null, notes: 'round-1 findings reused' }
    const rs = await parallel(LENS_NAMES.map(lens => () =>
      agent(findPrompt(it.file, lens), { label: `${lens}:${it.id}`, phase: 'Find', schema: REVIEW })))
    const seen = new Map()
    rs.forEach((r, i) => (r?.findings || []).forEach(f => {
      const k = key(f)
      if (!seen.has(k)) seen.set(k, { ...f, lens: [LENS_NAMES[i]] })
      else if (!seen.get(k).lens.includes(LENS_NAMES[i])) seen.get(k).lens.push(LENS_NAMES[i])
    }))
    return { id: it.id, file: it.file, seedFile: null, findings: [...seen.values()], notes: Object.fromEntries(rs.map((r, i) => [LENS_NAMES[i], r ? r.notes : 'AGENT FAILED'])) }
  },
  async r => {
    if (r.findings && !r.findings.length) return { id: r.id, findings: [], va: [], vb: [], notes: r.notes }
    const [a, b] = await parallel([
      () => agent(verifyPrompt(r.file, r.findings, 'acc', r.seedFile), { label: `verify-acc:${r.id}`, phase: 'Verify', schema: VERDICTS }),
      () => agent(verifyPrompt(r.file, r.findings, 'strict', r.seedFile), { label: `verify-strict:${r.id}`, phase: 'Verify', schema: VERDICTS }),
    ])
    return { id: r.id, findings: r.findings, va: a ? a.verdicts : null, vb: b ? b.verdicts : null, notes: r.notes }
  },
)
const ok = results.filter(Boolean)
const failed = ITEMS.map(i => i.id).filter(id => !ok.find(r => r.id === id))
const vfail = ok.filter(r => r.findings?.length !== 0 && (!r.va || !r.vb)).map(r => r.id)
if (failed.length) log(`FAILED items: ${failed.join(', ')}`)
if (vfail.length) log(`verifier failed for: ${vfail.join(', ')}`)
log(`done ${ok.length} passages`)
return { results: ok, failed, vfail }
