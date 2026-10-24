export const meta = {
  name: 'annotate-passages',
  description: 'Draft precise Chinese translation + dense vocabulary annotation for each passage, self-validated with check_ann.py',
  phases: [
    { title: 'Draft', detail: 'one annotator per passage writes ann draft and validates it' },
  ],
}

const REPO = args.repo || '/home/user/university-entrance-examination'
const SP = args.scratch
const OUT = args.out
const PIDS = args.pids

function prompt(pid) {
  return `You are annotating a gaokao (Chinese college entrance exam) English reading passage for senior-high students. The output drives a webpage and a video: each sentence is shown in English, with an exact Chinese translation below it and a list of highlighted vocabulary with glosses. The user demands ABSOLUTE precision: every translation must say exactly what the English says, in natural, idiomatic Chinese, and every gloss must give the exact sense used in that sentence.

INPUT: ${SP}/en_final/${pid}.txt — the passage, one numbered English sentence per line ("[n] EN: …"). The English is final (already corrected); do NOT change it.
STYLE EXAMPLES (read both fully first): ${REPO}/tools/ann/p61.txt and ${REPO}/tools/ann/p58.txt
OUTPUT: write the file ${OUT}/${pid}.txt (create the directory if needed). Do not modify any other file.

FILE FORMAT (exactly as in the examples):
T: <Chinese title, concise and specific, 6–20 characters, reflecting the main idea>
G: <体裁 · 主题, e.g. 说明文 · 科技与环保 / 议论文 · 社会与文化 / 记叙文 · 人物与观点>
S: <Chinese summary, 2–4 sentences, strictly faithful: no claims, causes or certainty the passage does not state>
then for every sentence n (1..N, same numbering and count as the input):
n <Chinese translation>
= entry | entry | entry …

ENTRY SYNTAX (the program matches the highlight automatically against the sentence):
- core word (新课标 senior-high syllabus word):  headword=pos. 释义      e.g. tackle=v. 应对；处理
- beyond-syllabus word:                          *headword=pos. 释义     e.g. *whereby=adv. 借此；凭借
- phrase / collocation / fixed pattern (NO pos):  ~phrase=释义           e.g. ~go about=忙于；做（日常事务）
- headword = dictionary form (verb base form, singular noun); inflected forms in the sentence (planting, studies, went, better…) are matched automatically.
- When the text differs from the headword in a way the matcher cannot derive (pronoun slots, irregular or contracted forms, possessives, parts that must be highlighted exactly), add the exact original text in braces: ~do one's part{doing its part}=尽自己的一份力 ; ~be committed to{committed to}=致力于 ; ~what's more{What’s more}=此外 (copy curly quotes exactly).
- Split phrases: use … in the headword for a gap: ~tear…down=拆除 ; ~not just…but=不仅……而且 ; and for braces use … between the exact pieces: ~pay attention to{pay…attention to}=关注.
- Participles used as adjectives before a noun take the participle as headword with adj.: existing=adj. 现有的 ; proposed=adj. 被提议的.
- pos labels: n. v. adj. adv. prep. conj. pron. num. det.
- No headword may overlap another entry's highlight in the same sentence (don't annotate "logical" separately if "~take…to its logical conclusion" covers it).

CONTENT RULES:
- Density: about one entry per 4–5 words of running text (≈70–100 entries for a 350-word passage). EVERY sentence must have at least one entry (iron rule), even short ones.
- Annotate the words a senior-high student needs to learn: core syllabus words that are not elementary (skip a/the/is/very/go/good etc.), all beyond-syllabus words worth knowing, and useful phrases/collocations/fixed patterns (including grammar patterns like the more…the more, little do they know (倒装)).
- Gloss = the sense used in THIS sentence first (you may add one closely related common sense after ；). Part of speech must match the use in this sentence. Do not list irrelevant senses (e.g. physical in "physical qualities of roots" = 形态的/形体的, not 物理的; settle for particles = 沉积, not 定居).
- Tier: 高中核心 only for words in the senior-high (新课标) word list; specialised/academic words (e.g. phenotype, isoprene, cortisol, astrophysics, cognitive, particle, scroll) are 超纲拓展 (*). Words the exam glosses with Chinese in parentheses are usually beyond the syllabus. Be consistent with the example files.
- Exam footnotes like "(认知的)" in the English are not part of the text to translate; just translate the word normally.

TRANSLATION RULES (lessons from previous reviews — follow all):
- Translate every clause: no omissions, no additions, no embellishment. Keep hedges and modality (may/might/could → 可能; if not higher → 甚至可能更高), degree words (only/just/even/almost/most/some), tense and aspect (is becoming → 正变得; has done → 一直/已经…), negation scope, comparatives, quantifiers, who does what to whom, pronoun referents, quotation boundaries (who said what).
- Multiples: "N times more/as many as X" → 是X的N倍 (NOT 比X多N倍). "as much as 30%" → 多达30%.
- Natural Chinese, not translationese: avoid stacked 的, 被…被, awkward 让…被; idioms rendered by meaning; but never paraphrase away meaning.
- Use full-width Chinese punctuation; quotation marks “ ”; consistent transliteration of each name throughout (常用译名 for well-known people/places; keep brand/app names like YouTube in English); numbers as in the English (Arabic numerals fine).
- A phrase that is highlighted and glossed should be recognisable in the translation (the student matches the gloss to the Chinese).
- Title and summary must be accurate and not overstate.
- IDIOMATIC CHINESE (地道) — the user demands translations a skilled native translator would write. Avoid translationese: English word order copied into Chinese; dashes copied from English parentheticals that split a verb from its object; overlong 的-chains; unnecessary 被 passives (prefer 存现句/主动); dangling 当……时 frames; noun-heavy renderings (导致了宇宙的创造 → 导致宇宙被创造出来); literal idioms (when it comes to ≠ 当它来到; feel like doing ≠ 感觉像); repeated 他/她/它/我们 where Chinese omits them; wrong connectors (instead = 就/转而 as alternative, not 反而 unless contrary to expectation); unidiomatic collocations (符合这首诗 → 符合诗中的意思; 一排排土壤 → 一垄垄的土地). Keep one consistent term for each concept across the whole passage (title and summary included), and make cross-sentence references (这/那/其/他们) point to the right thing. Read the whole passage at the end as one Chinese article and smooth anything that does not read naturally — without losing or adding any meaning.

PROCESS:
1. Read the input and both examples. 2. Write the full file. 3. Run: python3 ${SP}/check_ann.py ${pid} ${OUT}/${pid}.txt — it reports every highlight that cannot be found, sentences without entries, missing pos, phrase with pos, wrong sentence count. Fix and re-run until it prints OK. 4. Then re-read your whole file once more, comparing each Chinese line with its English clause by clause and each gloss with its sentence, and fix anything imprecise; re-run the check.
Return a one-line summary: the OK line from the checker and the number of entries.`
}

phase('Draft')
const results = await parallel(PIDS.map(pid => () => agent(prompt(pid), { label: `annotate:${pid}`, phase: 'Draft' })))
return PIDS.map((pid, i) => ({ pid, result: results[i] }))
