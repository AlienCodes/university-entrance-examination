# 声音对比（GPT-SoVITS 专属模型）

运行：`任务_sovits_老师8句-sovits-6`；8 句（t01 t02 t03 s1b1 s1b2 s1e s5bf s9e）；真声：05.wav
真声对照：相似度（真声两段之间）0.827；真声浊音基频中位数 112.5 Hz（协调会话给的 106.2 Hz）

| 候选 | 次 | 处理链与全部检查 | 基频 Hz | 与真声差（半音） | 与 106.2 Hz 差 | 相似度 | 英文部分相似度 | 识别错误率（SenseVoice） | 英文词错率（parakeet） |
|---|---|---|---|---|---|---|---|---|---|
| g1 | take1 | 全部通过 | 99.1 | -2.20 | -1.20 | 0.918 | 0.892 | 0.111 | 0.029 |
| g1 | take2 | 全部通过 | 98.0 | -2.40 | -1.40 | 0.917 | 0.884 | 0.096 | 0.029 |
| g1 | take3 | 全部通过 | 98.0 | -2.40 | -1.40 | 0.918 | 0.885 | 0.115 | 0.086 |
| g2 | take1 | 全部通过 | 107.4 | -0.80 | +0.20 | 0.932 | 0.873 | 0.092 | 0.114 |
| g2 | take2 | 全部通过 | 108.7 | -0.60 | +0.40 | 0.933 | 0.894 | 0.119 | 0.057 |
| g2 | take3 | 全部通过 | 109.3 | -0.50 | +0.50 | 0.929 | 0.872 | 0.096 | 0.029 |

## 每个候选每句最好的一次拼成一份

| 候选 | 处理链与全部检查 | MP3 | 每句用的是哪一次 |
|---|---|---|---|
| g1 | 全部通过 | 任务_sovits_老师8句-sovits-6_g1_每句最好.mp3 | t01:1 t02:1 t03:1 s1b1:2 s1b2:3 s1e:2 s5bf:1 s9e:2 |
| g2 | 全部通过 | 任务_sovits_老师8句-sovits-6_g2_每句最好.mp3 | t01:1 t02:1 t03:1 s1b1:3 s1b2:1 s1e:1 s5bf:3 s9e:2 |

## 每个小段的识别

| 候选 | 次 | 小段 | 错 / 字词数 | SenseVoice 识别 | parakeet 错词 |
|---|---|---|---|---|---|
| g1 | take1 | t01 | 0/28 | 好 那 接 下 来 我 们 就 开 始 讲 一 下 这 篇 二 零 二 六 年 新 课 标 一 卷 的 续 写 | — |
| g1 | take1 | t02 | 0/32 | 题 目 要 求 根 据 材 料 内 容 和 所 给 的 两 段 开 头 语 续 写 两 段 词 数 一 百 五 十 个 左 右 | — |
| g1 | take1 | t03 | 1/25 | 第 一 段 开 头 丹 尼 尔 和 瑞 秋 建 议 艾 米 丽 坐 火 车 继 续 他 的 旅 程 | — |
| g1 | take1 | s1b1 | 11/55 | 汉 英 的 时 候 我 们 按 逗 号 把 中 文 切 成 小 块 一 块 一 块 的 分 最 后 再 连 成 一 句 一 会 儿 他 们 几 着 说 讲 的 是 过 去 的 是 用 过 去 式 英 文 是 lay spa | — |
| g1 | take1 | s1b2 | 3/40 | 第 二 块 附 近 就 有 一 个 火 车 站 有 用 near 讲 的 是 过 去 所 以 用 words 附 近 nearby 放 在 句 尾 英 文 是 there was a station nearby | — |
| g1 | take1 | s1e | 4/16 | there was a station nearby they explained and a train to toronto with le | 1 |
| g1 | take1 | s5bf | 6/46 | 范 文 再 改 一 步 挥 手 和 人 类 是 同 时 发 生 的 做 事 的 都 是 艾 米 丽 把 wave 改 成 威 廉 放 在 句 首 做 伴 随 状 语 后 面 只 留 一 个 emily | — |
| g1 | take1 | s9e | 4/19 | emily handed them a box home made cookies and a car that red thank you for saving my holiday | 0 |
| g1 | take2 | t01 | 0/28 | 好 那 接 下 来 我 们 就 开 始 讲 一 下 这 篇 二 零 二 六 年 新 课 标 一 卷 的 续 写 | — |
| g1 | take2 | t02 | 0/32 | 题 目 要 求 根 据 材 料 内 容 和 所 给 的 两 段 开 头 语 续 写 两 段 词 数 一 百 五 十 个 左 右 | — |
| g1 | take2 | t03 | 1/25 | 第 一 段 开 头 丹 尼 尔 和 瑞 秋 建 议 艾 米 丽 坐 火 车 继 续 他 的 旅 程 | — |
| g1 | take2 | s1b1 | 4/55 | 汉 译 音 的 时 候 我 们 按 逗 号 把 中 文 切 成 小 块 一 块 一 块 的 翻 最 后 再 连 成 一 句 第 一 块 他 们 解 释 说 讲 的 是 过 去 的 事 用 过 去 式 英 文 是 they explain 的 | — |
| g1 | take2 | s1b2 | 5/40 | 第 二 块 附 近 就 有 一 个 火 车 站 有 用 there 必 讲 的 是 过 去 所 以 用 words 附 近 nearby 放 在 句 尾 英 文 是 there's station nearby | — |
| g1 | take2 | s1e | 1/16 | there was a station nearby they explained and the train to toronto would leave at noon | 1 |
| g1 | take2 | s5bf | 11/46 | 范 文 再 改 一 步 挥 手 和 人 类 是 同 时 发 生 的 做 事 的 都 是 艾 米 丽 把 维 微 带 成 维 微 放 在 句 首 做 伴 随 状 语 后 面 只 留 一 个 艾 米 丽 | — |
| g1 | take2 | s9e | 3/19 | emily handed them a box home made cookies and a car that read thank you for saving my holiday | 0 |
| g1 | take3 | t01 | 0/28 | 好 那 接 下 来 我 们 就 开 始 讲 一 下 这 篇 二 零 二 六 年 新 课 标 一 卷 的 续 写 | — |
| g1 | take3 | t02 | 1/32 | 题 目 要 求 根 据 材 料 内 容 和 所 给 的 两 段 开 头 语 是 写 两 段 词 数 一 百 五 十 个 左 右 | — |
| g1 | take3 | t03 | 1/25 | 第 一 段 开 头 丹 尼 尔 和 瑞 秋 建 议 艾 米 丽 坐 火 车 继 续 他 的 旅 程 | — |
| g1 | take3 | s1b1 | 7/55 | 汉 英 的 时 候 我 们 按 逗 号 把 中 文 切 成 小 块 一 块 一 块 的 翻 最 后 再 连 成 一 句 第 一 块 他 们 解 着 说 讲 的 是 过 去 的 事 用 过 去 时 英 是 they explain 的 | — |
| g1 | take3 | s1b2 | 2/40 | 第 二 块 附 近 就 有 一 个 火 车 站 有 用 there be 讲 的 是 过 去 所 以 用 words 附 近 nearby 放 在 句 尾 英 文 是 there is a station nearby | — |
| g1 | take3 | s1e | 5/16 | there was a station nearby they explained and the train took toronto over le were noon | 1 |
| g1 | take3 | s5bf | 10/46 | 范 文 在 哪 部 挥 手 和 人 类 是 同 时 发 生 的 做 事 的 都 是 艾 米 丽 把 wave 改 成 维 免 放 在 句 首 做 伴 随 状 语 后 面 只 留 一 个 emily | — |
| g1 | take3 | s9e | 4/19 | ammy handed them a box of home made cookies and a car that read thank you for saving my holiday | 2 |
| g2 | take1 | t01 | 0/28 | 好 那 接 下 来 我 们 就 开 始 讲 一 下 这 篇 二 零 二 六 年 新 课 标 一 卷 的 续 写 | — |
| g2 | take1 | t02 | 0/32 | 题 目 要 求 根 据 材 料 内 容 和 所 给 的 两 段 开 头 语 续 写 两 段 词 数 一 百 五 十 个 左 右 | — |
| g2 | take1 | t03 | 1/25 | 第 一 段 开 头 丹 尼 尔 和 瑞 秋 建 议 艾 米 丽 坐 火 车 继 续 他 的 旅 程 | — |
| g2 | take1 | s1b1 | 6/55 | 汉 语 音 的 时 候 我 们 按 逗 号 把 中 文 切 成 小 块 一 块 一 块 的 分 最 后 再 连 成 一 句 第 一 块 他 们 解 释 说 讲 的 是 过 去 的 时 用 过 去 式 英 文 是 they extend | — |
| g2 | take1 | s1b2 | 2/40 | 第 二 块 附 近 就 有 一 个 火 车 站 有 用 there be 讲 的 是 过 去 所 以 用 words 附 近 nearby 放 在 句 尾 英 文 是 there was station nearby | — |
| g2 | take1 | s1e | 1/16 | there was a station nearby they explained and the train to toronto would leave at noon | 1 |
| g2 | take1 | s5bf | 6/46 | 范 文 再 点 一 步 挥 手 和 人 类 是 同 时 发 生 的 做 事 的 都 是 艾 米 丽 把 wave 改 成 baby 放 在 句 首 做 伴 随 状 语 后 面 只 留 一 个 emily | — |
| g2 | take1 | s9e | 8/19 | d then handed them a box of home made cookies and called red thank you for saving my holiday | 3 |
| g2 | take2 | t01 | 2/28 | 好 那 接 下 来 我 们 就 开 始 讲 一 下 这 篇 二 零 二 六 年 新 课 标 一 卷 的 事 习 | — |
| g2 | take2 | t02 | 2/32 | 题 目 要 求 根 据 材 料 内 容 和 所 给 的 两 段 开 头 语 虚 写 两 段 次 数 一 百 五 十 个 左 右 | — |
| g2 | take2 | t03 | 1/25 | 第 一 段 开 头 丹 尼 尔 和 瑞 秋 建 议 艾 米 丽 坐 火 车 继 续 他 的 旅 程 | — |
| g2 | take2 | s1b1 | 8/55 | 汉 译 音 的 时 候 我 们 按 逗 号 把 中 文 切 成 小 块 一 块 一 块 的 翻 最 后 再 连 成 一 句 第 一 块 他 们 解 着 说 讲 的 是 过 去 的 是 用 过 去 式 英 文 式 的 explain 的 | — |
| g2 | take2 | s1b2 | 2/40 | 第 二 块 附 近 就 有 一 个 火 车 站 有 用 name 讲 的 是 过 去 所 以 用 was 附 近 nearby 放 在 句 尾 英 文 是 there was a station nearby | — |
| g2 | take2 | s1e | 6/16 | there was a stationed nearby they explained and train to toronto li we | 0 |
| g2 | take2 | s5bf | 6/46 | 范 文 再 改 一 步 挥 手 和 人 类 是 同 时 发 生 的 做 事 的 都 是 艾 米 丽 把 v 改 成 微 病 放 在 句 首 做 伴 随 状 语 后 面 只 留 一 个 emily | — |
| g2 | take2 | s9e | 4/19 | emily handed them a box of home made cookies and a car that red thank you for saving my holiday | 2 |
| g2 | take3 | t01 | 3/28 | 好 那 接 下 来 我 们 就 开 始 讲 一 下 这 篇 二 零 二 六 年 新 课 标 意 院 的 虚 写 | — |
| g2 | take3 | t02 | 0/32 | 题 目 要 求 根 据 材 料 内 容 和 所 给 的 两 段 开 头 语 续 写 两 段 词 数 一 百 五 十 个 左 右 | — |
| g2 | take3 | t03 | 1/25 | 第 一 段 开 头 丹 尼 尔 和 瑞 秋 建 议 艾 米 丽 坐 火 车 继 续 他 的 旅 程 | — |
| g2 | take3 | s1b1 | 5/55 | 汉 译 音 的 时 候 我 们 按 逗 号 把 中 文 切 成 小 块 一 块 一 块 的 分 最 后 再 连 成 一 句 第 一 块 他 们 解 着 说 讲 的 是 过 去 的 使 用 过 去 式 英 文 是 they explained | — |
| g2 | take3 | s1b2 | 3/40 | 第 二 块 附 近 就 有 一 个 火 车 站 有 用 never be 讲 的 是 过 去 所 以 用 words 附 近 nearby 放 在 句 尾 英 文 是 there is a station nearby | — |
| g2 | take3 | s1e | 2/16 | there was a stationed nearby they explained and the train to toronto would leave at noon | 1 |
| g2 | take3 | s5bf | 5/46 | 范 文 再 改 一 步 挥 手 和 忍 泪 是 同 时 发 生 的 做 事 的 都 是 艾 米 丽 把 wave 改 成 微 边 放 在 句 首 做 伴 随 状 语 后 面 只 留 一 个 enemy | — |
| g2 | take3 | s9e | 6/19 | emily handed them a box of home made cookies and car and red thank you for saving my holiday | 0 |
