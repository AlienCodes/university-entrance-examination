# 四级仔细阅读文章（Section C）

共 60 篇：每套真题的 Passage One 和 Passage Two（定题：2021 年 12 月只用第 1 套），只有文章，不含题目。每篇一个 `.txt`（段落之间空一行）；`passages.json` 与高考项目 `tools/passages.json` 格式相同，可直接走后续流程。


生成方法：`python3 四级/tools/extract_reading.py`（从 PDF 提取，按缩进分段，去页眉页脚）。2021 年的 4 套是扫描件，文字层识别错误多，已对照试卷页面逐字校对（`四级/tools/人工校对.json`）；中文注释统一为 “word (中文)”，引号撇号统一为弯引号，试卷本身的明显拼写错误已订正（如 Janiero → Janeiro，详见 原文订正记录.md）。

| 编号 | 年份 | 月份 | 套次 | 篇目 | 词数 | 段数 | 开头 |
|---|---|---|---|---|---|---|---|
| c01 | 2021 | 6 月 | 第 1 套 | Passage One | 351 | 5 | Educators and business leaders have more in common than it … |
| c02 | 2021 | 6 月 | 第 1 套 | Passage Two | 344 | 5 | Being an information technology, or IT, worker is not a job … |
| c03 | 2021 | 6 月 | 第 2 套 | Passage One | 343 | 7 | Sugar shocked. That describes the reaction of many … |
| c04 | 2021 | 6 月 | 第 2 套 | Passage Two | 351 | 6 | Success was once defined as being able to stay at a company … |
| c05 | 2021 | 6 月 | 第 3 套 | Passage One | 348 | 5 | Boredom has become trendy. Studies point to how boredom is … |
| c06 | 2021 | 6 月 | 第 3 套 | Passage Two | 345 | 7 | Can you remember what you ate yesterday? If asked, most … |
| c07 | 2021 | 12 月 | 第 1 套 | Passage One | 344 | 9 | As many office workers adapt to remote work, cities may … |
| c08 | 2021 | 12 月 | 第 1 套 | Passage Two | 336 | 8 | The human thirst for knowledge is the driving force behind … |
| c09 | 2022 | 6 月 | 第 1 套 | Passage One | 344 | 8 | Online classes began to be popularized just a few decades … |
| c10 | 2022 | 6 月 | 第 1 套 | Passage Two | 350 | 4 | In the age of the internet, there’s no such thing as a … |
| c11 | 2022 | 6 月 | 第 2 套 | Passage One | 351 | 6 | Social media can be a powerful communication tool for … |
| c12 | 2022 | 6 月 | 第 2 套 | Passage Two | 348 | 4 | In the coming era of budget cuts to education, distance … |
| c13 | 2022 | 12 月 | 第 1 套 | Passage One | 346 | 6 | To write his 2010 book, The 5-Factor World Diet, … |
| c14 | 2022 | 12 月 | 第 1 套 | Passage Two | 346 | 5 | Recognizing when a friend or colleague feels sad, angry or … |
| c15 | 2022 | 12 月 | 第 2 套 | Passage One | 343 | 8 | We’re eating more fish than ever these days. At around 20 … |
| c16 | 2022 | 12 月 | 第 2 套 | Passage Two | 331 | 5 | In 2020, the Nobel Peace Prize was awarded to the World … |
| c17 | 2022 | 12 月 | 第 3 套 | Passage One | 345 | 9 | Even though we are living in an age where growing old is … |
| c18 | 2022 | 12 月 | 第 3 套 | Passage Two | 349 | 9 | Research shows that in developed countries, more affluent … |
| c19 | 2023 | 6 月 | 第 1 套 | Passage One | 351 | 5 | The United States is facing a housing crisis: Affordable … |
| c20 | 2023 | 6 月 | 第 1 套 | Passage Two | 344 | 8 | Most of us in the entrepreneurial community are blessed—or … |
| c21 | 2023 | 6 月 | 第 2 套 | Passage One | 344 | 8 | Team-building exercises have become popular for managers … |
| c22 | 2023 | 6 月 | 第 2 套 | Passage Two | 349 | 5 | There are close to 58,000 homeless people in Los Angeles … |
| c23 | 2023 | 6 月 | 第 3 套 | Passage One | 351 | 5 | Supermarkets have long been suffering as one of the … |
| c24 | 2023 | 6 月 | 第 3 套 | Passage Two | 349 | 5 | The traditional school year, with three months of vacation … |
| c25 | 2023 | 12 月 | 第 1 套 | Passage One | 352 | 5 | One of my bad habits is saying “busy” when people ask me … |
| c26 | 2023 | 12 月 | 第 1 套 | Passage Two | 348 | 7 | Female employees consistently pay lower airfares than men … |
| c27 | 2023 | 12 月 | 第 2 套 | Passage One | 346 | 4 | Having a rival can keep you committed to achieving your … |
| c28 | 2023 | 12 月 | 第 2 套 | Passage Two | 340 | 5 | A multitasker is one who can perform two or more tasks … |
| c29 | 2023 | 12 月 | 第 3 套 | Passage One | 352 | 6 | In the history of horse racing, few horses have captured … |
| c30 | 2023 | 12 月 | 第 3 套 | Passage Two | 338 | 7 | People in business often make decisions based on their own … |
| c31 | 2024 | 6 月 | 第 1 套 | Passage One | 352 | 6 | People often wonder why some entrepreneurs have greater … |
| c32 | 2024 | 6 月 | 第 1 套 | Passage Two | 351 | 4 | Today, most scientific research is funded by government … |
| c33 | 2024 | 6 月 | 第 2 套 | Passage One | 351 | 6 | Lao Zi once said, “Care about what other people think and … |
| c34 | 2024 | 6 月 | 第 2 套 | Passage Two | 347 | 6 | Some people have said aging is more a slide into … |
| c35 | 2024 | 6 月 | 第 3 套 | Passage One | 347 | 5 | It may sound surprising, but you don’t have to be … |
| c36 | 2024 | 6 月 | 第 3 套 | Passage Two | 350 | 5 | The art of persuasion means convincing others to agree with … |
| c37 | 2024 | 12 月 | 第 1 套 | Passage One | 347 | 9 | As a university student, I’ve come to realise just how … |
| c38 | 2024 | 12 月 | 第 1 套 | Passage Two | 350 | 6 | Chocolates save us from many things, especially emotional … |
| c39 | 2024 | 12 月 | 第 2 套 | Passage One | 346 | 5 | The weakening of the human connection to nature might be … |
| c40 | 2024 | 12 月 | 第 2 套 | Passage Two | 347 | 9 | Engineering in the U.S. has long been a male-dominated … |
| c41 | 2024 | 12 月 | 第 3 套 | Passage One | 350 | 5 | Research in human-vehicle interaction has shown even … |
| c42 | 2024 | 12 月 | 第 3 套 | Passage Two | 350 | 10 | Do you ever blend up a protein drink for breakfast, or grab … |
| c43 | 2025 | 6 月 | 第 1 套 | Passage One | 343 | 9 | New research suggests that pandas may be at risk of dying … |
| c44 | 2025 | 6 月 | 第 1 套 | Passage Two | 347 | 5 | With those born with natural talents, it feels as if they … |
| c45 | 2025 | 6 月 | 第 2 套 | Passage One | 348 | 6 | We all make a little extra effort to look nice for special … |
| c46 | 2025 | 6 月 | 第 2 套 | Passage Two | 346 | 5 | With the rise of pop music, jazz, and electronic music, … |
| c47 | 2025 | 6 月 | 第 3 套 | Passage One | 351 | 7 | Our society places a high value on physical beauty. … |
| c48 | 2025 | 6 月 | 第 3 套 | Passage Two | 347 | 7 | Plant-based meats are coming soon to a dinner table near … |
| c49 | 2025 | 12 月 | 第 1 套 | Passage One | 347 | 6 | All living organisms on Earth are exposed to a 24-hour … |
| c50 | 2025 | 12 月 | 第 1 套 | Passage Two | 354 | 7 | Katharine Abraham, an economics professor, was chatting … |
| c51 | 2025 | 12 月 | 第 2 套 | Passage One | 350 | 5 | Junk food is now a staple of many Americans’ diets. … |
| c52 | 2025 | 12 月 | 第 2 套 | Passage Two | 345 | 8 | Adults dream during REM (rapid eye movement) sleep and … |
| c53 | 2025 | 12 月 | 第 3 套 | Passage One | 353 | 9 | New York’s Eleven Madison Park has become the first vegan … |
| c54 | 2025 | 12 月 | 第 3 套 | Passage Two | 352 | 7 | With genetic testing becoming increasingly popular, many … |
| c55 | 2026 | 6 月 | 第 1 套 | Passage One | 355 | 12 | Is organic food worth the higher price? It’s the classic … |
| c56 | 2026 | 6 月 | 第 1 套 | Passage Two | 354 | 7 | It is still controversial whether we are fundamentally … |
| c57 | 2026 | 6 月 | 第 2 套 | Passage One | 350 | 5 | People who systematically underestimate themselves and … |
| c58 | 2026 | 6 月 | 第 2 套 | Passage Two | 350 | 4 | Music is a universal language. In every culture and … |
| c59 | 2026 | 6 月 | 第 3 套 | Passage One | 354 | 8 | Disgust is a universal human emotion. One type of disgust … |
| c60 | 2026 | 6 月 | 第 3 套 | Passage Two | 354 | 5 | After finding out details about a stranger, we mistakenly … |
