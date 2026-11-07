# 声音对比（GPT-SoVITS 专属模型）

运行：`任务_sovits_老师8句_英文词-sovits-7`；8 句（t01 t02 t03 s1b1 s1b2 s1e s5bf s9e）；真声：05.wav
真声对照：相似度（真声两段之间）0.827；真声浊音基频中位数 112.5 Hz（协调会话给的 106.2 Hz）

| 候选 | 次 | 处理链与全部检查 | 基频 Hz | 与真声差（半音） | 与 106.2 Hz 差 | 相似度 | 英文部分相似度 | 识别错误率（SenseVoice） | 英文词错率（parakeet） |
|---|---|---|---|---|---|---|---|---|---|
| g1w | take1 | 拼接：相邻段语速差 1.44 倍（上限 1.38）：“re be,｜讲的是过去，”（29.2s）；相邻段语速差 2.62 倍（上限 1.38）：“过去，所以用｜was;”（30.66s）；相邻段语速差 1.56 倍（上限 1.38）：“was;｜附近，”（31.12s）；相邻段语速差 1.38 倍（上限 1.38）：“ | 99.7 | -2.10 | -1.10 | 0.918 | 0.875 | 0.092 | 0.122 |
| g1w | take2 | 拼接：相邻段语速差 1.44 倍（上限 1.38）：“车站。有，用｜there ”（28.11s）；相邻段语速差 1.46 倍（上限 1.38）：“re be,｜讲的是过去，”（28.64s）；相邻段语速差 2.39 倍（上限 1.38）：“过去，所以用｜was;”（30.16s）；相邻段语速差 1.67 倍（上限 1 | 100.8 | -1.90 | -0.90 | 0.918 | 0.879 | 0.111 | 0.143 |
| g1w | take3 | 拼接：相邻段语速差 1.45 倍（上限 1.38）：“车站。有，用｜there ”（28.37s）；相邻段语速差 1.51 倍（上限 1.38）：“re be,｜讲的是过去，”（28.9s）；相邻段语速差 2.89 倍（上限 1.38）：“过去，所以用｜was;”（30.38s）；相邻段语速差 2.24 倍（上限 1. | 99.4 | -2.15 | -1.15 | 0.914 | 0.880 | 0.146 | 0.184 |
| g2w | take1 | 拼接：相邻段语速差 2.36 倍（上限 1.38）：“过去，所以用｜was;”（30.74s）；相邻段语速差 1.47 倍（上限 1.38）：“was;｜附近，”（31.22s）；相邻段语速差 1.70 倍（上限 1.38）：“附近，｜nearby”（32.07s）；相邻段语速差 2.86 倍（上限 1.38）：“ea | 109.3 | -0.50 | +0.50 | 0.927 | 0.877 | 0.130 | 0.245 |
| g2w | take2 | 拼接：相邻段语速差 1.51 倍（上限 1.38）：“式。英文是：｜They e”（25.66s）；相邻段语速差 2.17 倍（上限 1.38）：“过去，所以用｜was;”（31.79s）；相邻段语速差 1.52 倍（上限 1.38）：“was;｜附近，”（32.24s）；相邻段语速差 1.42 倍（上限 1.38）： | 111.9 | -0.10 | +0.90 | 0.929 | 0.893 | 0.126 | 0.184 |
| g2w | take3 | 拼接：相邻段语速差 1.51 倍（上限 1.38）：“车站。有，用｜there ”（29.68s）；相邻段语速差 1.60 倍（上限 1.38）：“re be,｜讲的是过去，”（30.28s）；相邻段语速差 2.74 倍（上限 1.38）：“过去，所以用｜was;”（31.86s）；相邻段语速差 1.96 倍（上限 1 | 109.9 | -0.40 | +0.60 | 0.923 | 0.877 | 0.161 | 0.122 |

## 每个候选每句最好的一次拼成一份

| 候选 | 处理链与全部检查 | MP3 | 每句用的是哪一次 |
|---|---|---|---|
| g1w | 拼接：相邻段语速差 1.44 倍（上限 1.38）：“re be,｜讲的是过去，”（29.33s）；相邻段语速差 2.50 倍（上限 1.38）：“过去，所以用｜was;”（30.79s）；相邻段语速差 1.48 倍（上限 1.38）：“was;｜附近，”（31.23s）；相邻段语速差 1.40 倍（上限 1.38）： | — | t01:1 t02:1 t03:2 s1b1~1:1 s1b1~2:1 s1b2~1:1 s1b2~2:1 s1b2~3:1 s1b2~4:2 s1b2~5:1 s1b2~6:1 s1b2~7:3 s1b2~8:2 s1e:2 s5bf~1:1 s5bf~2:2 s5bf~3:1 s5bf~4:1 s5bf~5:1 s5bf~6:1 s9e:2 |
| g2w | 拼接：相邻段语速差 1.57 倍（上限 1.38）：“车站。有，用｜there ”（28.22s）；相邻段语速差 1.50 倍（上限 1.38）：“re be,｜讲的是过去，”（28.82s）；相邻段语速差 2.36 倍（上限 1.38）：“过去，所以用｜was;”（30.49s）；相邻段语速差 1.63 倍（上限 1 | — | t01:1 t02:1 t03:1 s1b1~1:2 s1b1~2:1 s1b2~1:2 s1b2~2:3 s1b2~3:1 s1b2~4:1 s1b2~5:2 s1b2~6:1 s1b2~7:1 s1b2~8:1 s1e:1 s5bf~1:2 s5bf~2:2 s5bf~3:2 s5bf~4:1 s5bf~5:1 s5bf~6:1 s9e:2 |

## 每个小段的识别

| 候选 | 次 | 小段 | 错 / 字词数 | SenseVoice 识别 | parakeet 错词 |
|---|---|---|---|---|---|
| g1w | take1 | t01 | 0/28 | 好 那 接 下 来 我 们 就 开 始 讲 一 下 这 篇 二 零 二 六 年 新 课 标 一 卷 的 续 写 | — |
| g1w | take1 | t02 | 0/32 | 题 目 要 求 根 据 材 料 内 容 和 所 给 的 两 段 开 头 语 续 写 两 段 词 数 一 百 五 十 个 左 右 | — |
| g1w | take1 | t03 | 2/25 | 第 段 开 头 丹 尼 尔 和 瑞 秋 建 议 艾 米 丽 坐 火 车 继 续 他 的 旅 程 | — |
| g1w | take1 | s1b1~1 | 2/53 | 汉 英 的 时 候 我 们 按 逗 号 把 中 文 切 成 小 块 一 块 一 块 的 翻 最 后 再 连 成 一 句 第 一 块 他 们 解 释 说 讲 的 是 过 去 的 事 用 过 去 式 英 文 是 | — |
| g1w | take1 | s1b1~2 | 0/2 | they explained | 0 |
| g1w | take1 | s1b2~1 | 1/14 | 第 二 块 附 近 就 有 一 个 火 车 站 有 应 | — |
| g1w | take1 | s1b2~2 | 1/2 | 那 be | 0 |
| g1w | take1 | s1b2~3 | 0/8 | 讲 的 是 过 去 所 以 用 | — |
| g1w | take1 | s1b2~4 | 1/1 |  | 1 |
| g1w | take1 | s1b2~5 | 0/2 | 附 近 | — |
| g1w | take1 | s1b2~6 | 0/1 | nearby | 0 |
| g1w | take1 | s1b2~7 | 1/7 | 放 在 句 尾 英 文 时 | — |
| g1w | take1 | s1b2~8 | 0/5 | there was a station nearby | 1 |
| g1w | take1 | s1e | 4/16 | there was a station nearby they explained and a train to toronto with levi no no | 1 |
| g1w | take1 | s5bf~1 | 3/26 | 范 文 再 改 一 步 挥 手 和 人 类 是 同 时 发 生 的 做 事 的 都 是 艾 米 丽 吧 | — |
| g1w | take1 | s5bf~2 | 2/1 | 妹 子 | 3 |
| g1w | take1 | s5bf~3 | 0/2 | 改 成 | — |
| g1w | take1 | s5bf~4 | 1/1 | vaving | 0 |
| g1w | take1 | s5bf~5 | 1/15 | 放 在 句 首 做 伴 随 状 语 后 面 只 留 一 个 | — |
| g1w | take1 | s5bf~6 | 1/1 | ie | 0 |
| g1w | take1 | s9e | 4/19 | emily handed them a box home made cookies and a car that red thank you for saving my holiday | 0 |
| g1w | take2 | t01 | 0/28 | 好 那 接 下 来 我 们 就 开 始 讲 一 下 这 篇 二 零 二 六 年 新 课 标 一 卷 的 续 写 | — |
| g1w | take2 | t02 | 0/32 | 题 目 要 求 根 据 材 料 内 容 和 所 给 的 两 段 开 头 语 续 写 两 段 词 数 一 百 五 十 个 左 右 | — |
| g1w | take2 | t03 | 1/25 | 第 一 段 开 头 丹 尼 尔 和 瑞 秋 建 议 艾 米 丽 坐 火 车 继 续 他 的 旅 程 | — |
| g1w | take2 | s1b1~1 | 6/53 | 汉 一 音 的 时 候 我 们 按 逗 号 把 中 文 切 成 小 块 一 块 一 块 的 翻 最 后 再 连 成 一 句 第 一 块 他 们 解 释 说 讲 的 是 过 去 的 时 用 过 去 时 英 文 式 | — |
| g1w | take2 | s1b1~2 | 1/2 | they screamed | 1 |
| g1w | take2 | s1b2~1 | 2/14 | 第 二 会 儿 附 近 就 有 一 个 火 车 站 有 用 | — |
| g1w | take2 | s1b2~2 | 2/2 |  | 2 |
| g1w | take2 | s1b2~3 | 0/8 | 讲 的 是 过 去 所 以 用 | — |
| g1w | take2 | s1b2~4 | 1/1 | what | 0 |
| g1w | take2 | s1b2~5 | 0/2 | 附 近 | — |
| g1w | take2 | s1b2~6 | 0/1 | nearby | 0 |
| g1w | take2 | s1b2~7 | 1/7 | 放 在 句 尾 英 文 时 | — |
| g1w | take2 | s1b2~8 | 0/5 | there was a station nearby | 0 |
| g1w | take2 | s1e | 1/16 | there was a station nearby they explained and the train to toronto would leave at noon | 1 |
| g1w | take2 | s5bf~1 | 3/26 | 范 文 再 改 一 步 挥 手 和 人 类 是 同 时 发 生 的 做 事 的 都 是 艾 米 丽 吧 | — |
| g1w | take2 | s5bf~2 | 2/1 | 妹 ve | 1 |
| g1w | take2 | s5bf~3 | 2/2 | 给 钟 | — |
| g1w | take2 | s5bf~4 | 1/1 | livaving | 1 |
| g1w | take2 | s5bf~5 | 2/15 | 放 在 狙 首 做 伴 随 状 语 后 面 只 留 一 个 | — |
| g1w | take2 | s5bf~6 | 1/1 |  | 1 |
| g1w | take2 | s9e | 3/19 | emily handed them a box home made cookies and a car that read thank you for saving my holiday | 0 |
| g1w | take3 | t01 | 0/28 | 好 那 接 下 来 我 们 就 开 始 讲 一 下 这 篇 二 零 二 六 年 新 课 标 一 卷 的 续 写 | — |
| g1w | take3 | t02 | 1/32 | 题 目 要 求 根 据 材 料 内 容 和 所 给 的 两 段 开 头 语 是 写 两 段 词 数 一 百 五 十 个 左 右 | — |
| g1w | take3 | t03 | 1/25 | 第 一 段 开 头 丹 尼 尔 和 瑞 秋 建 议 艾 米 丽 坐 火 车 继 续 他 的 旅 程 | — |
| g1w | take3 | s1b1~1 | 6/53 | 汉 译 英 的 时 候 我 们 都 要 把 中 文 切 成 小 块 一 块 一 块 的 分 最 后 再 连 成 一 句 第 一 块 他 们 解 释 说 讲 的 是 过 去 的 事 用 过 去 式 英 文 式 | — |
| g1w | take3 | s1b1~2 | 1/2 | y explained | 0 |
| g1w | take3 | s1b2~1 | 1/14 | 第 二 排 附 近 就 有 一 个 火 车 站 有 用 | — |
| g1w | take3 | s1b2~2 | 2/2 | 那 b | 2 |
| g1w | take3 | s1b2~3 | 0/8 | 讲 的 是 过 去 所 以 用 | — |
| g1w | take3 | s1b2~4 | 1/1 | wa | 0 |
| g1w | take3 | s1b2~5 | 2/2 | 父 人 | — |
| g1w | take3 | s1b2~6 | 0/1 | nearby | 0 |
| g1w | take3 | s1b2~7 | 0/7 | 放 在 句 尾 英 文 是 | — |
| g1w | take3 | s1b2~8 | 0/5 | there was a station nearby | 0 |
| g1w | take3 | s1e | 6/16 | there was a station nearby they explained and the train took toronto over li weonon | 1 |
| g1w | take3 | s5bf~1 | 4/26 | 范 围 再 改 一 步 挥 手 和 人 类 是 同 时 发 生 的 做 事 的 都 是 艾 米 丽 吧 | — |
| g1w | take3 | s5bf~2 | 3/1 | 没 有 的 | 1 |
| g1w | take3 | s5bf~3 | 2/2 | 点 虫 | — |
| g1w | take3 | s5bf~4 | 2/1 | 没 aving | 1 |
| g1w | take3 | s5bf~5 | 1/15 | 放 在 句 首 做 伴 随 状 语 后 面 只 留 一 个 | — |
| g1w | take3 | s5bf~6 | 1/1 | me | 2 |
| g1w | take3 | s9e | 4/19 | ammy handed them a box of home made cookies and a car that read thank you for saving my holiday | 2 |
| g2w | take1 | t01 | 0/28 | 好 那 接 下 来 我 们 就 开 始 讲 一 下 这 篇 二 零 二 六 年 新 课 标 一 卷 的 续 写 | — |
| g2w | take1 | t02 | 0/32 | 题 目 要 求 根 据 材 料 内 容 和 所 给 的 两 段 开 头 语 续 写 两 段 词 数 一 百 五 十 个 左 右 | — |
| g2w | take1 | t03 | 1/25 | 第 一 段 开 头 丹 尼 尔 和 瑞 秋 建 议 艾 米 丽 坐 火 车 继 续 他 的 旅 程 | — |
| g2w | take1 | s1b1~1 | 4/53 | 汉 英 的 时 候 我 们 按 逗 号 把 中 文 切 小 块 一 块 一 块 的 分 最 后 再 连 成 一 句 第 一 块 他 们 解 释 说 讲 的 是 过 去 的 事 用 过 去 式 英 文 是 | — |
| g2w | take1 | s1b1~2 | 0/2 | they explained | 0 |
| g2w | take1 | s1b2~1 | 2/14 | 第 二 款 附 近 就 一 个 火 车 站 有 用 | — |
| g2w | take1 | s1b2~2 | 2/2 | nerly | 2 |
| g2w | take1 | s1b2~3 | 0/8 | 讲 的 是 过 去 所 以 用 | — |
| g2w | take1 | s1b2~4 | 1/1 | wa | 0 |
| g2w | take1 | s1b2~5 | 2/2 | fujin | — |
| g2w | take1 | s1b2~6 | 2/1 | 年 年 | 1 |
| g2w | take1 | s1b2~7 | 0/7 | 放 在 句 尾 英 文 是 | — |
| g2w | take1 | s1b2~8 | 0/5 | there was a station nearby | 0 |
| g2w | take1 | s1e | 1/16 | there was a station nearby they explained and the train to toronto would leave at noon | 1 |
| g2w | take1 | s5bf~1 | 4/26 | 范 文 在 哪 一 步 挥 手 和 忍 类 是 同 时 发 生 的 做 事 的 都 是 艾 米 丽 吧 | — |
| g2w | take1 | s5bf~2 | 2/1 | 妹 子 | 3 |
| g2w | take1 | s5bf~3 | 1/2 | 点 成 | — |
| g2w | take1 | s5bf~4 | 2/1 | 妹 妹 | 1 |
| g2w | take1 | s5bf~5 | 1/15 | 放 在 句 首 做 伴 随 状 语 后 面 只 留 一 个 | — |
| g2w | take1 | s5bf~6 | 1/1 | deally | 1 |
| g2w | take1 | s9e | 8/19 | d then handed them a box of home made cookies and called red thank you for saving my holiday | 3 |
| g2w | take2 | t01 | 1/28 | 好 那 接 下 来 我 们 就 开 始 讲 一 下 这 篇 二 零 二 六 年 新 课 标 一 卷 的 事 写 | — |
| g2w | take2 | t02 | 2/32 | 题 目 要 求 根 据 材 料 内 容 和 所 给 的 两 段 开 头 语 虚 写 两 段 次 数 一 百 五 十 个 左 右 | — |
| g2w | take2 | t03 | 1/25 | 第 一 段 开 头 丹 尼 尔 和 瑞 秋 建 议 艾 米 丽 坐 火 车 继 续 他 的 旅 程 | — |
| g2w | take2 | s1b1~1 | 3/53 | 汉 译 音 的 时 候 我 们 按 逗 号 把 中 文 切 成 小 块 一 块 一 块 的 分 最 后 再 连 成 一 句 第 一 块 他 们 解 释 说 讲 的 是 过 去 的 事 用 过 去 式 英 文 是 | — |
| g2w | take2 | s1b1~2 | 2/2 | y explained 的 | 0 |
| g2w | take2 | s1b2~1 | 1/14 | 第 二 款 附 近 就 有 一 个 火 车 站 有 用 | — |
| g2w | take2 | s1b2~2 | 2/2 | dmi | 2 |
| g2w | take2 | s1b2~3 | 0/8 | 讲 的 是 过 去 所 以 用 | — |
| g2w | take2 | s1b2~4 | 1/1 | once | 0 |
| g2w | take2 | s1b2~5 | 0/2 | 附 近 | — |
| g2w | take2 | s1b2~6 | 2/1 | new 掰 | 2 |
| g2w | take2 | s1b2~7 | 0/7 | 放 在 句 尾 英 文 是 | — |
| g2w | take2 | s1b2~8 | 0/5 | there was a station nearby | 0 |
| g2w | take2 | s1e | 6/16 | there was a stationed nearby they explained and train to toronto li weon | 0 |
| g2w | take2 | s5bf~1 | 3/26 | 范 文 再 给 一 步 挥 手 和 忍 类 是 同 时 发 生 的 做 事 的 都 是 艾 米 丽 爸 | — |
| g2w | take2 | s5bf~2 | 1/1 | wave | 1 |
| g2w | take2 | s5bf~3 | 0/2 | 改 成 | — |
| g2w | take2 | s5bf~4 | 2/1 | we 问 | 1 |
| g2w | take2 | s5bf~5 | 1/15 | 放 在 句 首 做 伴 随 状 语 后 面 只 留 一 个 | — |
| g2w | take2 | s5bf~6 | 1/1 | family | 1 |
| g2w | take2 | s9e | 4/19 | emily handed them a box of home made cookies and a car that red thank you for saving my holiday | 2 |
| g2w | take3 | t01 | 3/28 | 好 那 接 下 来 我 们 就 开 始 讲 一 下 这 篇 二 零 二 六 年 新 课 标 意 院 的 虚 写 | — |
| g2w | take3 | t02 | 0/32 | 题 目 要 求 根 据 材 料 内 容 和 所 给 的 两 段 开 头 语 续 写 两 段 词 数 一 百 五 十 个 左 右 | — |
| g2w | take3 | t03 | 1/25 | 第 一 段 开 头 丹 尼 尔 和 瑞 秋 建 议 艾 米 丽 坐 火 车 继 续 他 的 旅 程 | — |
| g2w | take3 | s1b1~1 | 5/53 | 汉 语 英 的 时 候 我 们 按 逗 号 把 中 文 切 成 小 块 一 块 一 块 的 分 最 后 再 连 成 一 句 一 块 他 们 解 释 说 讲 的 是 过 去 的 事 用 过 去 式 英 文 式 | — |
| g2w | take3 | s1b1~2 | 2/2 | that explain | 0 |
| g2w | take3 | s1b2~1 | 1/14 | 第 二 款 附 近 就 有 一 个 火 车 站 有 用 | — |
| g2w | take3 | s1b2~2 | 2/2 | nbe | 0 |
| g2w | take3 | s1b2~3 | 0/8 | 讲 的 是 过 去 所 以 用 | — |
| g2w | take3 | s1b2~4 | 2/1 | 袜 子 | 0 |
| g2w | take3 | s1b2~5 | 0/2 | 附 近 | — |
| g2w | take3 | s1b2~6 | 4/1 | new 掰 new by | 1 |
| g2w | take3 | s1b2~7 | 0/7 | 放 在 句 尾 英 文 是 | — |
| g2w | take3 | s1b2~8 | 0/5 | there was a station nearby | 0 |
| g2w | take3 | s1e | 2/16 | there was a stationed nearby they explained and the train to toronto would leave at noon | 1 |
| g2w | take3 | s5bf~1 | 4/26 | 范 伦 再 改 一 步 挥 手 和 人 类 是 同 时 发 生 的 做 事 的 都 是 艾 米 丽 吧 | — |
| g2w | take3 | s5bf~2 | 2/1 | ma 子 | 1 |
| g2w | take3 | s5bf~3 | 2/2 | 诞 生 | — |
| g2w | take3 | s5bf~4 | 2/1 | we 问 | 2 |
| g2w | take3 | s5bf~5 | 3/15 | 放 在 巨 手 座 伴 随 状 语 后 面 只 留 一 个 | — |
| g2w | take3 | s5bf~6 | 1/1 | family | 1 |
| g2w | take3 | s9e | 6/19 | emily handed them a box of home made cookies and car and red thank you for saving my holiday | 0 |
