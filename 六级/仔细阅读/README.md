# 六级仔细阅读文章（Section C）

共 58 篇：每套真题的 Passage One 和 Passage Two（29 套全部收录），只有文章，不含题目。每篇一个 `.txt`（段落之间空一行）；`passages.json` 与高考项目 `tools/passages.json` 格式相同，可直接走后续流程。


生成方法：`python3 六级/tools/extract_reading.py`（从 PDF 提取，按缩进分段，去页眉页脚）。2021 年 12 月、2022 年 6 月的 5 套是扫描件，对照试卷页面逐字校对（`六级/tools/人工校对.json`）；中文注释统一为 “word (中文)”，引号撇号统一为弯引号，试卷本身的错误订正见 原文订正记录.md。

| 编号 | 年份 | 月份 | 套次 | 篇目 | 词数 | 段数 | 开头 |
|---|---|---|---|---|---|---|---|
| s01 | 2021 | 12 月 | 第 1 套 | Passage One | 448 | 6 | Social media is absolutely everywhere. Billions of people … |
| s02 | 2021 | 12 月 | 第 1 套 | Passage Two | 455 | 7 | In recent years, the food industry has increased its use of … |
| s03 | 2021 | 12 月 | 第 2 套 | Passage One | 440 | 4 | The trend toward rationality and enlightenment was … |
| s04 | 2021 | 12 月 | 第 2 套 | Passage Two | 451 | 5 | According to a recent study, a small but growing proportion … |
| s05 | 2021 | 12 月 | 第 3 套 | Passage One | 447 | 7 | The subject of automation and its role in our economy has … |
| s06 | 2021 | 12 月 | 第 3 套 | Passage Two | 446 | 9 | Look at the people around you. Some are passive, others … |
| s07 | 2022 | 6 月 | 第 1 套 | Passage One | 448 | 7 | Selective colleges and universities in the U.S. are under … |
| s08 | 2022 | 6 月 | 第 1 套 | Passage Two | 448 | 7 | When a group of Australians was asked why they believed … |
| s09 | 2022 | 6 月 | 第 2 套 | Passage One | 446 | 5 | Since American idol star Taryn Southern started composing … |
| s10 | 2022 | 6 月 | 第 2 套 | Passage Two | 444 | 6 | A few weeks ago, a well-meaning professor tried to explain … |
| s11 | 2022 | 12 月 | 第 1 套 | Passage One | 445 | 6 | Many people associate their self-worth with their work. The … |
| s12 | 2022 | 12 月 | 第 1 套 | Passage Two | 442 | 7 | Degradation of the world’s natural resources by humans is … |
| s13 | 2022 | 12 月 | 第 2 套 | Passage One | 445 | 7 | Some people in the US have asserted that forgiving student … |
| s14 | 2022 | 12 月 | 第 2 套 | Passage Two | 450 | 9 | If there’s one rule that most parents cling to in the … |
| s15 | 2022 | 12 月 | 第 3 套 | Passage One | 444 | 4 | How can one person enjoy good health, while another person … |
| s16 | 2022 | 12 月 | 第 3 套 | Passage Two | 440 | 9 | Scientists have created by accident an enzyme (酶) that … |
| s17 | 2023 | 6 月 | 第 1 套 | Passage One | 448 | 9 | Technology is never a neutral tool for achieving human … |
| s18 | 2023 | 6 月 | 第 1 套 | Passage Two | 452 | 6 | Phonics, which involves sounding out words syllable (音节) by … |
| s19 | 2023 | 6 月 | 第 2 套 | Passage One | 450 | 5 | If you’re someone who has turned to snacking on junk food … |
| s20 | 2023 | 6 月 | 第 2 套 | Passage Two | 440 | 11 | Chimpanzees (黑猩猩), human beings’ closest animal relatives, … |
| s21 | 2023 | 6 月 | 第 3 套 | Passage One | 450 | 8 | How on earth did we come to this? We protect our children … |
| s22 | 2023 | 6 月 | 第 3 套 | Passage Two | 450 | 7 | Many oppose workplace surveillance, because of the inherent … |
| s23 | 2023 | 12 月 | 第 1 套 | Passage One | 450 | 13 | One of the great successes of the Republican Party in … |
| s24 | 2023 | 12 月 | 第 1 套 | Passage Two | 444 | 8 | Journal editors decide what gets published and what … |
| s25 | 2023 | 12 月 | 第 2 套 | Passage One | 451 | 8 | Could you get by without using the internet for four and a … |
| s26 | 2023 | 12 月 | 第 2 套 | Passage Two | 445 | 4 | Psychologists have long been in disagreement as to whether … |
| s27 | 2023 | 12 月 | 第 3 套 | Passage One | 448 | 12 | Research is meant to benefit society by raising public … |
| s28 | 2023 | 12 月 | 第 3 套 | Passage Two | 448 | 6 | Spiders make their presence felt in late August and through … |
| s29 | 2024 | 6 月 | 第 1 套 | Passage One | 442 | 9 | Sarcasm and jazz have something surprisingly in common: You … |
| s30 | 2024 | 6 月 | 第 1 套 | Passage Two | 444 | 11 | Variability is crucially important for learning new skills. … |
| s31 | 2024 | 6 月 | 第 2 套 | Passage One | 446 | 9 | It is irrefutable that employees know the difference … |
| s32 | 2024 | 6 月 | 第 2 套 | Passage Two | 446 | 9 | The term “environmentalist” can mean different things. It … |
| s33 | 2024 | 6 月 | 第 3 套 | Passage One | 447 | 9 | The “American Dream” promises that in the Land of … |
| s34 | 2024 | 6 月 | 第 3 套 | Passage Two | 448 | 4 | When someone asks us “what do you do?” we nearly always … |
| s35 | 2024 | 12 月 | 第 1 套 | Passage One | 447 | 13 | Imagine you’re an alien sent to Earth to document the … |
| s36 | 2024 | 12 月 | 第 1 套 | Passage Two | 450 | 9 | An awakening has been taking place in the physical world … |
| s37 | 2024 | 12 月 | 第 2 套 | Passage One | 450 | 7 | With population increases and global urbanisation ever … |
| s38 | 2024 | 12 月 | 第 2 套 | Passage Two | 447 | 10 | Statements, like “beauty is in the eye of the beholder … |
| s39 | 2024 | 12 月 | 第 3 套 | Passage One | 446 | 7 | There are hundreds of personality quizzes online that … |
| s40 | 2024 | 12 月 | 第 3 套 | Passage Two | 448 | 9 | One hundred thirty-five students, four teachers, one giant … |
| s41 | 2025 | 6 月 | 第 1 套 | Passage One | 443 | 13 | Nationally, one in six children miss 15 or more days of … |
| s42 | 2025 | 6 月 | 第 1 套 | Passage Two | 450 | 10 | After earning a bachelor’s degree, I was determined to do … |
| s43 | 2025 | 6 月 | 第 2 套 | Passage One | 450 | 7 | Simulators are most often utilized within industries such … |
| s44 | 2025 | 6 月 | 第 2 套 | Passage Two | 439 | 7 | GDP growth is not a good indicator of how well a country is … |
| s45 | 2025 | 6 月 | 第 3 套 | Passage One | 448 | 8 | Why are we so worried about our careers? Partly it’s to do … |
| s46 | 2025 | 6 月 | 第 3 套 | Passage Two | 448 | 10 | Women have historically been paid less. But in the US in … |
| s47 | 2025 | 12 月 | 第 1 套 | Passage One | 448 | 10 | Many see friendships as a comfort blanket: a shoulder to … |
| s48 | 2025 | 12 月 | 第 1 套 | Passage Two | 449 | 9 | During his acceptance speech for the Nobel Peace Prize, … |
| s49 | 2025 | 12 月 | 第 2 套 | Passage One | 442 | 7 | As interdependent beings we cannot thrive independent of … |
| s50 | 2025 | 12 月 | 第 2 套 | Passage Two | 444 | 9 | People who repeatedly give unwanted advice can be … |
| s51 | 2025 | 12 月 | 第 3 套 | Passage One | 451 | 9 | Mindfulness has been shown to have a number of meaningful … |
| s52 | 2025 | 12 月 | 第 3 套 | Passage Two | 447 | 7 | The other day I had to log into a service I hadn’t used … |
| s53 | 2026 | 6 月 | 第 1 套 | Passage One | 447 | 5 | Children’s use of social media is a problem. That doesn’t … |
| s54 | 2026 | 6 月 | 第 1 套 | Passage Two | 443 | 9 | About a decade ago, the G-20, a forum of the world’s … |
| s55 | 2026 | 6 月 | 第 2 套 | Passage One | 448 | 7 | What does self-discipline look like at work? Sometimes, … |
| s56 | 2026 | 6 月 | 第 2 套 | Passage Two | 444 | 8 | Smartphones have always posed challenges for parents of … |
| s57 | 2026 | 6 月 | 第 3 套 | Passage One | 444 | 9 | Three artists have brought a lawsuit against Stability AL, … |
| s58 | 2026 | 6 月 | 第 3 套 | Passage Two | 448 | 8 | On a warm October morning, Daniel Agok woke up to another … |
