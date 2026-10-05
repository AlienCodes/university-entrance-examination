# 四级仔细阅读文章（Section C）

共 62 篇：每套真题的 Passage One 和 Passage Two，只有文章，不含题目。每篇一个 `.txt`（段落之间空一行）；`passages.json` 与高考项目 `tools/passages.json` 格式相同，可直接走后续流程。


生成方法：`python3 四级/tools/extract_reading.py`（从 PDF 提取，按缩进分段，去页眉页脚）。2021 年 6 套是扫描件，文字层识别错误多，已对照试卷页面逐字校对（`四级/tools/人工校对.json`）；中文注释统一为 “word (中文)”，引号撇号统一为弯引号，试卷本身的明显拼写错误已订正（如 check-kissing → cheek-kissing、Janiero → Janeiro）。

| 编号 | 年份 | 月份 | 套次 | 篇目 | 词数 | 段数 | 开头 |
|---|---|---|---|---|---|---|---|
| c01 | 2021 | 6 月 | 第 1 套 | Passage One | 351 | 5 | Educators and business leaders have more in common than it … |
| c02 | 2021 | 6 月 | 第 1 套 | Passage Two | 342 | 5 | Being an information technology, or IT, worker is not a job … |
| c03 | 2021 | 6 月 | 第 2 套 | Passage One | 343 | 7 | Sugar shocked. That describes the reaction of many … |
| c04 | 2021 | 6 月 | 第 2 套 | Passage Two | 351 | 6 | Success was once defined as being able to stay at a company … |
| c05 | 2021 | 6 月 | 第 3 套 | Passage One | 348 | 5 | Boredom has become trendy. Studies point to how boredom is … |
| c06 | 2021 | 6 月 | 第 3 套 | Passage Two | 345 | 7 | Can you remember what you ate yesterday? If asked, most … |
| c07 | 2021 | 12 月 | 第 1 套 | Passage One | 341 | 9 | As many office workers adapt to remote work, cities may … |
| c08 | 2021 | 12 月 | 第 1 套 | Passage Two | 336 | 8 | The human thirst for knowledge is the driving force behind … |
| c09 | 2021 | 12 月 | 第 2 套 | Passage One | 350 | 4 | With obesity now affecting 29% of the population in … |
| c10 | 2021 | 12 月 | 第 2 套 | Passage Two | 346 | 6 | Nationwide, only about three percent of early childhood … |
| c11 | 2021 | 12 月 | 第 3 套 | Passage One | 346 | 7 | Have you ever wondered how acceptable it is to hug or touch … |
| c12 | 2021 | 12 月 | 第 3 套 | Passage Two | 354 | 5 | From climate change to the ongoing pandemic (大流行病) and … |
| c13 | 2022 | 6 月 | 第 1 套 | Passage One | 346 | 8 | Online classes began to be popularized just a few decades … |
| c14 | 2022 | 6 月 | 第 1 套 | Passage Two | 348 | 4 | In the age of the internet, there’s no such thing as a … |
| c15 | 2022 | 6 月 | 第 2 套 | Passage One | 351 | 6 | Social media can be a powerful communication tool for … |
| c16 | 2022 | 6 月 | 第 2 套 | Passage Two | 348 | 4 | In the coming era of budget cuts to education, distance … |
| c17 | 2022 | 12 月 | 第 1 套 | Passage One | 344 | 6 | To write his 2010 book, The 5-Factor World Diet, … |
| c18 | 2022 | 12 月 | 第 1 套 | Passage Two | 343 | 5 | Recognizing when a friend or colleague feels sad, angry or … |
| c19 | 2022 | 12 月 | 第 2 套 | Passage One | 343 | 8 | We’re eating more fish than ever these days. At around 20 … |
| c20 | 2022 | 12 月 | 第 2 套 | Passage Two | 332 | 5 | In 2020, the Nobel Peace Prize was awarded to the World … |
| c21 | 2022 | 12 月 | 第 3 套 | Passage One | 344 | 9 | Even though we are living in an age where growing old is … |
| c22 | 2022 | 12 月 | 第 3 套 | Passage Two | 350 | 9 | Research shows that in developed countries, more affluent … |
| c23 | 2023 | 6 月 | 第 1 套 | Passage One | 351 | 5 | The United States is facing a housing crisis: Affordable … |
| c24 | 2023 | 6 月 | 第 1 套 | Passage Two | 344 | 8 | Most of us in the entrepreneurial community are blessed—or … |
| c25 | 2023 | 6 月 | 第 2 套 | Passage One | 345 | 8 | Team-building exercises have become popular for managers … |
| c26 | 2023 | 6 月 | 第 2 套 | Passage Two | 347 | 5 | There are close to 58,000 homeless people in Los Angeles … |
| c27 | 2023 | 6 月 | 第 3 套 | Passage One | 349 | 5 | Supermarkets have long been suffering as one of the … |
| c28 | 2023 | 6 月 | 第 3 套 | Passage Two | 348 | 5 | The traditional school year, with three months of vacation … |
| c29 | 2023 | 12 月 | 第 1 套 | Passage One | 352 | 5 | One of my bad habits is saying “busy” when people ask me … |
| c30 | 2023 | 12 月 | 第 1 套 | Passage Two | 348 | 7 | Female employees consistently pay lower airfares than men … |
| c31 | 2023 | 12 月 | 第 2 套 | Passage One | 348 | 4 | Having a rival can keep you committed to achieving your … |
| c32 | 2023 | 12 月 | 第 2 套 | Passage Two | 343 | 5 | A multitasker is one who can perform two or more tasks … |
| c33 | 2023 | 12 月 | 第 3 套 | Passage One | 352 | 6 | In the history of horse racing, few horses have captured … |
| c34 | 2023 | 12 月 | 第 3 套 | Passage Two | 343 | 7 | People in business often make decisions based on their own … |
| c35 | 2024 | 6 月 | 第 1 套 | Passage One | 349 | 6 | People often wonder why some entrepreneurs have greater … |
| c36 | 2024 | 6 月 | 第 1 套 | Passage Two | 352 | 4 | Today, most scientific research is funded by government … |
| c37 | 2024 | 6 月 | 第 2 套 | Passage One | 350 | 6 | Lao Zi once said, “Care about what other people think and … |
| c38 | 2024 | 6 月 | 第 2 套 | Passage Two | 350 | 6 | Some people have said aging is more a slide into … |
| c39 | 2024 | 6 月 | 第 3 套 | Passage One | 349 | 5 | It may sound surprising, but you don’t have to be … |
| c40 | 2024 | 6 月 | 第 3 套 | Passage Two | 349 | 5 | The art of persuasion means convincing others to agree with … |
| c41 | 2024 | 12 月 | 第 1 套 | Passage One | 349 | 9 | As a university student, I’ve come to realise just how … |
| c42 | 2024 | 12 月 | 第 1 套 | Passage Two | 352 | 6 | Chocolates save us from many things, especially emotional … |
| c43 | 2024 | 12 月 | 第 2 套 | Passage One | 346 | 5 | The weakening of the human connection to nature might be … |
| c44 | 2024 | 12 月 | 第 2 套 | Passage Two | 347 | 9 | Engineering in the U.S. has long been a male-dominated … |
| c45 | 2024 | 12 月 | 第 3 套 | Passage One | 350 | 5 | Research in human-vehicle interaction has shown even … |
| c46 | 2024 | 12 月 | 第 3 套 | Passage Two | 350 | 10 | Do you ever blend up a protein drink for breakfast, or grab … |
| c47 | 2025 | 6 月 | 第 1 套 | Passage One | 343 | 9 | New research suggests that pandas may be at risk of dying … |
| c48 | 2025 | 6 月 | 第 1 套 | Passage Two | 345 | 5 | With those born with natural talents, it feels as if they … |
| c49 | 2025 | 6 月 | 第 2 套 | Passage One | 349 | 6 | We all take a little extra effort to look nice for special … |
| c50 | 2025 | 6 月 | 第 2 套 | Passage Two | 348 | 5 | With the rise of pop music, jazz, and electronic music, … |
| c51 | 2025 | 6 月 | 第 3 套 | Passage One | 351 | 7 | Our society places a high value on physical beauty. … |
| c52 | 2025 | 6 月 | 第 3 套 | Passage Two | 347 | 7 | Plant-based meats are coming soon to a dinner table near … |
| c53 | 2025 | 12 月 | 第 1 套 | Passage One | 347 | 6 | All living organisms on Earth are exposed to a 24-hour … |
| c54 | 2025 | 12 月 | 第 1 套 | Passage Two | 355 | 7 | Katharine Abraham, an economics professor, was chatting … |
| c55 | 2025 | 12 月 | 第 2 套 | Passage One | 351 | 5 | Junk food is now a staple of many Americans’ diets. … |
| c56 | 2025 | 12 月 | 第 2 套 | Passage Two | 348 | 8 | Adults dream during REM (rapid eye movement) sleep and … |
| c57 | 2025 | 12 月 | 第 3 套 | Passage One | 353 | 9 | New York’s Eleven Madison Park has become the first vegan … |
| c58 | 2025 | 12 月 | 第 3 套 | Passage Two | 352 | 7 | With genetic testing becoming increasingly popular, many … |
| c59 | 2026 | 6 月 | 第 2 套 | Passage One | 351 | 5 | People who systematically underestimate themselves and … |
| c60 | 2026 | 6 月 | 第 2 套 | Passage Two | 350 | 4 | Music is a universal language. In every culture and … |
| c61 | 2026 | 6 月 | 第 3 套 | Passage One | 352 | 8 | Disgust is a universal human emotion. One type of disgust … |
| c62 | 2026 | 6 月 | 第 3 套 | Passage Two | 352 | 5 | After finding out details about a stranger, we mistakenly … |
