export const meta = {
  name: 'tem8-annotate',
  description: 'Draft precise, idiomatic Chinese translation + vocabulary annotation for TEM-8 Reading Section A passages, each self-validated with check_ann.py',
  phases: [{ title: 'Draft', detail: 'one annotator per passage writes the annotation file and validates it to OK' }],
}
const REPO = args.repo
const SP = args.scratch
const OUT = args.out
const IDS = args.ids

function prompt(id) {
  return `You are translating and annotating a reading passage from China's Test for English Majors Band 8 (TEM-8, 英语专业八级, Reading Comprehension Section A) for Chinese English-major students preparing for TEM-8. The output drives a study webpage and a video: each sentence is shown in English, with an exact Chinese translation below it and the highlighted vocabulary with glosses. The user demands ABSOLUTE precision AND idiomatic Chinese: every translation must say exactly what the English says, and read like natural Chinese written by a skilled translator; every gloss must give the exact sense used in that sentence.

INPUT: ${SP}/t8en/${id}.txt — the passage, one numbered English sentence per line ("[n] EN: …"), with paragraph markers. The English is final (already proofread and sealed); do NOT change it.
STYLE EXAMPLES (read both fully first — same file format; these are the final, multi-round-reviewed CET-4 files of this project, so follow their translation quality, gloss style and density): ${REPO}/四级/ann/c60.txt and ${REPO}/四级/ann/c52.txt
OUTPUT: write the file ${OUT}/${id}.txt (create the directory if needed). Do not modify any other file.

FILE FORMAT (exactly as in the examples):
T: <Chinese title, concise and specific, 6–20 characters, reflecting the main idea>
G: <体裁 · 主题, e.g. 说明文 · 科技与健康 / 议论文 · 社会与文化 / 记叙文 · 人物与经历>
S: <Chinese summary, 2–4 sentences, strictly faithful: no claims, causes or certainty the passage does not state>
then for every sentence n (1..N, same numbering and count as the input; paragraph markers are NOT written):
n <Chinese translation>
= entry | entry | entry …

ENTRY SYNTAX (the program matches the highlight automatically against the sentence):
- single word:                                          headword=pos. 释义      e.g. tackle=v. 应对；处理 ; obesity=n. 肥胖（症）
- phrase / collocation / fixed pattern (NO pos, at least two words):  ~phrase=释义   e.g. ~go about=忙于；做（日常事务）
- The user does NOT want any distinction between TEM-8 syllabus words and beyond-syllabus (超纲) words: NEVER use the * prefix (every single word is written without a prefix).
- headword = dictionary form (verb base form, singular noun); inflected forms in the sentence (planting, studies, went, better…) are matched automatically.
- When the text differs from the headword in a way the matcher cannot derive (pronoun slots, irregular or contracted forms, possessives, parts that must be highlighted exactly), add the exact original text in braces: ~do one's part{doing its part}=尽自己的一份力 ; ~be committed to{committed to}=致力于 ; ~what's more{What’s more}=此外 (copy curly quotes exactly).
- Split phrases: use … in the headword for a gap: ~tear…down=拆除 ; ~not only…but also=不仅……而且 ; and for braces use … between the exact pieces: ~pay attention to{pay…attention to}=关注.
- Participles used as adjectives before a noun take the participle as headword with adj.: existing=adj. 现有的 ; processed=adj. 加工过的.
- pos labels: n. v. adj. adv. prep. conj. pron. num. det.
- No headword may overlap another entry's highlight in the same sentence. No duplicate headwords within one sentence.

CONTENT RULES (what to annotate — the user's explicit instruction: "不要考虑超纲词汇，把每一句话里面有必要记住的生词全部做出来"):
- Target learner: a Chinese English-major student preparing for TEM-8 who wants to memorise EVERY word and phrase in each sentence that is worth remembering. In EVERY sentence, annotate ALL such words and phrases — be exhaustive, sentence by sentence. Whether a word is inside or beyond the TEM-8 syllabus does not matter at all: if a learner needs to remember it to understand and recite this sentence (including technical terms, names of things, and words the exam footnotes), annotate it.
- Skip only truly elementary words that every English major already knows (a/the/is/have/do/go/good/very/many/people/school/time/day/like/want and similar junior-high basics), unless such a word is used in an unusual sense or inside a fixed phrase. When in doubt, annotate.
- The user's examples: words like "participant" and "interact" MUST be annotated — not one such word may be missed. The checker enforces this: every word in a sentence that is not in the basic list (${REPO}/四级/tools/基础词.txt: junior-high words + the 1000 most frequent English words, with their regular inflections) must be covered by an entry's highlight in THAT sentence (proper nouns, numbers and all-caps abbreviations excepted). It reports "漏标" with the missing words; annotate them (as a single word, or inside a correct phrase entry). A word that recurs in several sentences must be annotated in each sentence where it occurs.
- Also annotate useful phrases/collocations/fixed patterns (verb + preposition, noun + preposition, idioms, grammar patterns such as not only…but also, so…that, inversion like Gone are the days…).
- EVERY sentence must have at least one entry (iron rule), even short ones.
- Gloss = the sense used in THIS sentence first (you may add one closely related common sense after ；). Part of speech must match the use in this sentence. Do not list irrelevant senses.
- A highlighted word/phrase must be the exact word in this sentence that carries the glossed sense (do not highlight noun "matters" with the verb sense "要紧").
- Do NOT mark free combinations as phrases (e.g. "around them", "across languages", "matter more"); phrases are fixed collocations/idioms/patterns.
- The exam's Chinese footnotes in parentheses like "(权衡)" are part of the printed English; do not translate them separately and do not annotate them, but DO annotate the English word they gloss (with your own precise gloss).

TRANSLATION RULES (lessons from many review rounds — follow ALL):
- Translate every clause: no omissions, no additions, no embellishment. Keep hedges and modality (may/might/could → 可能/或许; should → 应该), degree words (only/just/even/almost/most/some/slightly), tense and aspect (is becoming → 正变得; has done → 一直/已经…), negation scope (all…not / not all), comparatives (less likely → 可能性更小, NOT 不太可能; much less often → 少得多), superlatives (no 最 unless the English has most/-est), quantifiers, who does what to whom, pronoun referents, quotation boundaries (only the speaker's words inside “ ”; words added by the translator go outside).
- Multiples: "N times more/as many as X" → 是X的N倍 (NOT 比X多N倍). "as much as 30%" → 多达30%. at best → 往好里说也…… (not 充其量).
- Natural Chinese (地道), not translationese. Avoid: English word order copied into Chinese; overlong 的-chains and two 的 in a row; 被/被…所… passives where Chinese uses active or 存现句; 进行+动词; nominalisations (……的推出); dangling 当……时 frames; redundant 他/她/它/我们/他们 that Chinese omits; literal idioms (when it comes to ≠ 当它来到); wrong connectors (instead = 而是/转而, not 反而 unless contrary to expectation); unidiomatic collocations; dashes copied from English that split a verb from its object. But never paraphrase away meaning.
- Use full-width Chinese punctuation (，。；：？！、“”‘’（）——); consistent transliteration of each name throughout (常用通行译名 for well-known people, places, organisations; keep brand/app names like LinkedIn, YouTube in English); numbers as in the English. Keep one consistent term for each concept across the whole passage (title and summary included), and make cross-sentence references (这/那/其/他们) point to the right thing.
- A highlighted and glossed phrase should be recognisable in the translation (the student matches the gloss to the Chinese).
- Title and summary must be accurate and not overstate.
- LITERARY EXCERPTS (many TEM-8 passages come from novels, memoirs and essays): translate in a literary register that is faithful to the author's voice, imagery and rhythm (dialogue sounds like speech, description stays vivid), but still clause by clause with nothing added or lost.

PROCESS:
1. Read the input and both examples. 2. Write the full file. 3. Run: /opt/ttsenv/bin/python ${REPO}/专八/tools/check_ann.py ${id} ${OUT}/${id}.txt — it reports every highlight that cannot be found, sentences without entries, missing/extra pos, one-word "phrases", any * prefix, Chinese punctuation problems, words that are not in the basic list but are not annotated (漏标), wrong sentence count. Fix and re-run until it prints OK.
4. Then re-read your whole file once more as a strict reviewer: compare each Chinese line with its English clause by clause (meaning, modality, degree, tense, negation, numbers, names) and each gloss with its sentence; then read the Chinese alone, as one article, and smooth anything that does not read naturally — without losing or adding any meaning. Re-run the check until OK.
Return a one-line summary: the OK line from the checker.`
}

phase('Draft')
const results = await parallel(IDS.map(id => () => agent(prompt(id), { label: `annotate:${id}`, phase: 'Draft' })))
return IDS.map((id, i) => ({ id, result: results[i] }))
