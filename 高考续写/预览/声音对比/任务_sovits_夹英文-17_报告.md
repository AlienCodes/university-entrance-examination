# 夹英文对比：mx1（g1）对 mxlt（g1 + top_k 10 温度 0.8），运行 #17

4 段（s1b1 s1b3 s1h s1p2）各 3 次，每次中文段里夹的英文共 41 词；数字都由 声音对比.py 量出，下面是 3 次平均。

| 候选 | 处理链与全部检查通过 | 相似度（门槛 0.88） | SenseVoice 识别错误率 | 中文段里夹的英文 错词率（parakeet） | 同（whisper） |
|---|---|---|---|---|---|
| mx1 | 3/3 | 0.911 | 0.159 | 0.707 | 0.447 |
| mxlt | 1/3 | 0.915 | 0.133 | 0.577 | 0.464 |

**判定：保持现状**（整片中文段不加 `gen`，只英文段用 `gen_en`）。理由：①夹英文两个识别器结论相反（parakeet mxlt 好 0.13，whisper mx1 好 0.02），每处只有 2—9 个词、截出的片段常整段认不出（8/8），不算“明显好”；②mxlt 3 次里 2 次拼接检查不过（相邻段语速差 1.41、1.46 倍，上限 1.38），mx1 3/3 通过——中文这一项变差；相似度、SenseVoice 两项 mxlt 略好，但都在 3 次之间的波动范围内。

给老师对比听（每段挑最好的一次拼成一份，完整处理链 + 全部检查通过，带合格证）：`任务_sovits_夹英文-17_mx1_每句最好.mp3`、`任务_sovits_夹英文-17_mxlt_每句最好.mp3`。

---

# 声音对比（GPT-SoVITS 专属模型）

运行：`任务_sovits_夹英文-17`；4 句（s1b1 s1b3 s1p2 s1h）；真声：05.wav
真声对照：相似度（真声两段之间）0.827；真声浊音基频中位数 112.5 Hz（协调会话给的 106.2 Hz）

| 候选 | 次 | 处理链与全部检查 | 基频 Hz | 与真声差（半音） | 与 106.2 Hz 差 | 相似度 | 英文部分相似度 | 识别错误率（SenseVoice） | 英文词错率（parakeet） | 英文词错率（whisper） | 中文段里夹的英文 错词率（parakeet） | 同（whisper） |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mx1 | take1 | 全部通过 | 96.8 | -2.60 | -1.60 | 0.909 | — | 0.152 | — | — | 0.439 | 0.390 |
| mx1 | take2 | 全部通过 | 100.8 | -1.90 | -0.90 | 0.909 | — | 0.173 | — | — | 1.000 | 0.488 |
| mx1 | take3 | 全部通过 | 100.8 | -1.90 | -0.90 | 0.916 | — | 0.152 | — | — | 0.683 | 0.463 |
| mxlt | take1 | 全部通过 | 99.7 | -2.10 | -1.10 | 0.916 | — | 0.130 | — | — | 0.488 | 0.415 |
| mxlt | take2 | 拼接：相邻段语速差 1.41 倍（上限 1.38）：“ained。｜第三块：中午”（12.47s），未输出 | 99.7 | -2.10 | -1.10 | 0.915 | — | 0.117 | — | — | 0.585 | 0.537 |
| mxlt | take3 | 拼接：相邻段语速差 1.46 倍（上限 1.38）：“与原文融洽。｜这句话还有别”（36.11s），未输出 | 99.1 | -2.20 | -1.20 | 0.913 | — | 0.152 | — | — | 0.659 | 0.439 |

## 每个候选每句最好的一次拼成一份

| 候选 | 处理链与全部检查 | MP3 | 每句用的是哪一次 |
|---|---|---|---|
| mx1 | 全部通过 | 任务_sovits_夹英文-17_mx1_每句最好.mp3 | s1b1~1:1 s1b1~2:3 s1b1~3:2 s1b1~4:1 s1b3~1:3 s1b3~2:2 s1b3~3:3 s1p2~1:1 s1p2~2:1 s1p2~3:1 s1h~1:2 s1h~2:1 s1h~3:2 |
| mxlt | 全部通过 | 任务_sovits_夹英文-17_mxlt_每句最好.mp3 | s1b1~1:2 s1b1~2:1 s1b1~3:1 s1b1~4:2 s1b3~1:1 s1b3~2:1 s1b3~3:1 s1p2~1:2 s1p2~2:2 s1p2~3:2 s1h~1:2 s1h~2:1 s1h~3:2 |

## 中文段里夹的英文（对齐截出，英文识别器再认）

| 候选 | 次 | 小段 | 英文 | 错 / 词数（parakeet） | parakeet 识别 | 错（whisper） |
|---|---|---|---|---|---|---|
| mx1 | take1 | s1b1~4 | they explained | 1/2 | should they spin | 1 |
| mx1 | take1 | s1b3~2 | a train to toronto | 4/4 |  | 4 |
| mx1 | take1 | s1b3~2 | would leave | 2/2 | i'm not sure if | 1 |
| mx1 | take1 | s1b3~3 | a train to toronto would leave at noon | 8/8 |  | 4 |
| mx1 | take1 | s1p2~1 | a train to toronto would leave at noon | 0/8 | a train to toronto would leave at noon | 1 |
| mx1 | take1 | s1h~2 | the nearest station was just a short drive away | 2/9 | the nearest station was just a short driveway | 2 |
| mx1 | take1 | s1h~3 | a train would leave for toronto at noon | 1/8 | a train would leave for the until at noon | 3 |
| mx1 | take2 | s1b1~4 | they explained | 2/2 |  | 2 |
| mx1 | take2 | s1b3~2 | a train to toronto | 4/4 |  | 2 |
| mx1 | take2 | s1b3~2 | would leave | 2/2 | i'm not sure if | 2 |
| mx1 | take2 | s1b3~3 | a train to toronto would leave at noon | 8/8 |  | 4 |
| mx1 | take2 | s1p2~1 | a train to toronto would leave at noon | 8/8 |  | 5 |
| mx1 | take2 | s1h~2 | the nearest station was just a short drive away | 9/9 |  | 4 |
| mx1 | take2 | s1h~3 | a train would leave for toronto at noon | 8/8 |  | 1 |
| mx1 | take3 | s1b1~4 | they explained | 0/2 | they explained | 1 |
| mx1 | take3 | s1b3~2 | a train to toronto | 4/4 |  | 3 |
| mx1 | take3 | s1b3~2 | would leave | 2/2 |  | 1 |
| mx1 | take3 | s1b3~3 | a train to toronto would leave at noon | 8/8 |  | 4 |
| mx1 | take3 | s1p2~1 | a train to toronto would leave at noon | 4/8 | they are a train to the ronto would revenue | 3 |
| mx1 | take3 | s1h~2 | the nearest station was just a short drive away | 2/9 | the nearest station was just a short driveway | 2 |
| mx1 | take3 | s1h~3 | a train would leave for toronto at noon | 8/8 |  | 5 |
| mxlt | take1 | s1b1~4 | they explained | 2/2 | manage the explain | 1 |
| mxlt | take1 | s1b3~2 | a train to toronto | 4/4 |  | 0 |
| mxlt | take1 | s1b3~2 | would leave | 2/2 | young leaves | 2 |
| mxlt | take1 | s1b3~3 | a train to toronto would leave at noon | 1/8 | each train to toronto would leave at noon | 4 |
| mxlt | take1 | s1p2~1 | a train to toronto would leave at noon | 1/8 | a train to toronto will leave at noon | 2 |
| mxlt | take1 | s1h~2 | the nearest station was just a short drive away | 2/9 | the nearest station was just a shoulder away between | 4 |
| mxlt | take1 | s1h~3 | a train would leave for toronto at noon | 8/8 |  | 4 |
| mxlt | take2 | s1b1~4 | they explained | 0/2 | they explained | 1 |
| mxlt | take2 | s1b3~2 | a train to toronto | 4/4 | hocho | 4 |
| mxlt | take2 | s1b3~2 | would leave | 1/2 | will leave | 1 |
| mxlt | take2 | s1b3~3 | a train to toronto would leave at noon | 8/8 |  | 5 |
| mxlt | take2 | s1p2~1 | a train to toronto would leave at noon | 8/8 |  | 5 |
| mxlt | take2 | s1h~2 | the nearest station was just a short drive away | 2/9 | the nearest station was just a short dark drawing to itin | 2 |
| mxlt | take2 | s1h~3 | a train would leave for toronto at noon | 1/8 | he said a train would leave for dauto at noon | 4 |
| mxlt | take3 | s1b1~4 | they explained | 0/2 | should they explained | 1 |
| mxlt | take3 | s1b3~2 | a train to toronto | 4/4 | huju | 1 |
| mxlt | take3 | s1b3~2 | would leave | 1/2 | will leave | 1 |
| mxlt | take3 | s1b3~3 | a train to toronto would leave at noon | 8/8 |  | 6 |
| mxlt | take3 | s1p2~1 | a train to toronto would leave at noon | 8/8 |  | 3 |
| mxlt | take3 | s1h~2 | the nearest station was just a short drive away | 2/9 | the nearest station was just a short drop draw | 2 |
| mxlt | take3 | s1h~3 | a train would leave for toronto at noon | 4/8 | he said a train would be for the auto afternoon | 4 |

## 每个小段的识别

| 候选 | 次 | 小段 | 错 / 字词数 | SenseVoice 识别 | parakeet 错词 |
|---|---|---|---|---|---|
| mx1 | take1 | s1b1~1 | 2/8 | 怎 么 把 它 它 翻 译 成 英 文 | — |
| mx1 | take1 | s1b1~2 | 2/26 | 我 们 按 逗 号 把 中 文 切 成 鸡 小 块 一 块 一 块 的 翻 最 后 再 连 成 一 句 | — |
| mx1 | take1 | s1b1~3 | 3/19 | 也 快 他 们 解 释 说 讲 的 是 过 去 的 事 用 过 去 式 | — |
| mx1 | take1 | s1b1~4 | 2/5 | 英 文 是 this swing | — |
| mx1 | take1 | s1b3~1 | 3/16 | 第 三 份 中 午 有 一 趟 太 阳 多 伦 多 的 火 车 | — |
| mx1 | take1 | s1b3~2 | 2/34 | 开 往 多 伦 多 的 火 车 就 是 i train to toronto 火 车 中 午 才 开 这 是 站 在 过 去 说 将 来 所 以 用 will leave | — |
| mx1 | take1 | s1b3~3 | 7/11 | 因 为 是 a train to toronto 物 理 员 能 弄 | — |
| mx1 | take1 | s1p2~1 | 2/12 | 得 分 点 二 a train to toronto would leave a new | — |
| mx1 | take1 | s1p2~2 | 0/25 | 地 点 时 间 都 具 体 方 案 才 可 信 原 文 说 离 目 的 地 还 有 一 百 英 里 | — |
| mx1 | take1 | s1p2~3 | 1/24 | 这 句 就 把 怎 么 去 的 问 题 解 决 了 对 应 第 一 条 与 原 文 融 洽 | — |
| mx1 | take1 | s1h~1 | 2/9 | 这 种 外 还 有 别 的 写 法 | — |
| mx1 | take1 | s1h~2 | 5/27 | 前 半 句 可 以 写 the nearest station was show 大 卓 为 最 近 的 车 站 开 车 一 会 儿 就 到 | — |
| mx1 | take1 | s1h~3 | 4/15 | 后 半 句 也 可 以 写 a train would leave for the on and no | — |
| mx1 | take2 | s1b1~1 | 4/8 | 整 把 的 翻 罪 英 文 | — |
| mx1 | take2 | s1b1~2 | 3/26 | 我 们 按 逗 号 把 钟 切 成 几 小 块 一 块 一 块 的 翻 最 后 再 连 成 一 句 | — |
| mx1 | take2 | s1b1~3 | 0/19 | 第 一 块 他 们 解 释 说 讲 的 是 过 去 的 事 用 过 去 式 | — |
| mx1 | take2 | s1b1~4 | 2/5 | 英 文 是 they explain 的 | — |
| mx1 | take2 | s1b3~1 | 1/16 | 第 三 份 中 午 有 一 趟 开 往 多 伦 多 的 火 车 | — |
| mx1 | take2 | s1b3~2 | 1/34 | 开 往 多 伦 多 的 火 车 就 是 a train to toronto 火 车 中 午 才 开 这 是 站 在 过 去 说 将 来 所 以 用 我 leave | — |
| mx1 | take2 | s1b3~3 | 6/11 | 英 文 是 h three to toronto will live 能 | — |
| mx1 | take2 | s1p2~1 | 4/12 | 得 分 点 二 a train to toronto will leave i no no | — |
| mx1 | take2 | s1p2~2 | 1/25 | 地 点 时 间 都 具 体 方 案 才 可 行 原 文 说 离 目 的 地 还 有 一 百 英 里 | — |
| mx1 | take2 | s1p2~3 | 3/24 | 这 一 局 就 把 怎 么 去 的 问 题 解 决 了 对 应 第 一 条 语 圆 文 融 洽 | — |
| mx1 | take2 | s1h~1 | 0/9 | 这 句 话 还 有 别 的 写 法 | — |
| mx1 | take2 | s1h~2 | 12/27 | 前 面 就 可 以 写 的 nearest 死 c 政 我 招 所 受 w v 最 近 的 车 站 开 车 一 会 儿 就 到 | — |
| mx1 | take2 | s1h~3 | 3/15 | 后 半 句 可 said a train would leave for toronto at noon | — |
| mx1 | take3 | s1b1~1 | 4/8 | 怎 么 把 它 范 正 因 为 | — |
| mx1 | take3 | s1b1~2 | 1/26 | 我 们 按 逗 号 把 中 文 切 成 几 小 块 一 块 一 块 的 翻 最 后 再 连 成 一 句 | — |
| mx1 | take3 | s1b1~3 | 0/19 | 第 一 块 他 们 解 释 说 讲 的 是 过 去 的 事 用 过 去 式 | — |
| mx1 | take3 | s1b1~4 | 2/5 | 英 文 是 they explain 的 | — |
| mx1 | take3 | s1b3~1 | 0/16 | 第 三 块 中 午 有 一 趟 开 往 多 伦 多 的 火 车 | — |
| mx1 | take3 | s1b3~2 | 2/34 | 开 往 多 伦 多 的 火 车 就 是 train to toronto 火 车 中 午 才 开 就 是 站 在 过 去 说 将 来 所 以 用 would leave | — |
| mx1 | take3 | s1b3~3 | 3/11 | 英 文 是 a train to toronto would 理 外 弄 | — |
| mx1 | take3 | s1p2~1 | 8/12 | 得 分 点 二 a train to 到 ron 座 我 的 李 外 no | — |
| mx1 | take3 | s1p2~2 | 1/25 | 地 点 时 间 都 具 体 方 案 才 可 信 原 文 说 离 目 的 地 还 有 一 百 公 里 | — |
| mx1 | take3 | s1p2~3 | 2/24 | 这 一 句 就 把 怎 么 去 的 问 题 解 决 了 对 应 第 一 条 与 园 林 融 洽 | — |
| mx1 | take3 | s1h~1 | 0/9 | 这 句 话 还 有 别 的 写 法 | — |
| mx1 | take3 | s1h~2 | 5/27 | 前 面 就 可 以 写 the nearest station was just a show 到 最 近 的 车 站 开 车 一 会 儿 就 到 | — |
| mx1 | take3 | s1h~3 | 7/15 | 后 半 句 也 可 以 写 a trim folder under in | — |
| mxlt | take1 | s1b1~1 | 2/8 | 怎 么 把 他 胎 翻 成 英 文 | — |
| mxlt | take1 | s1b1~2 | 1/26 | 我 们 按 逗 号 把 中 文 切 成 几 小 块 一 块 一 块 的 翻 最 后 再 连 成 一 句 | — |
| mxlt | take1 | s1b1~3 | 0/19 | 第 一 块 他 们 解 释 说 讲 的 是 过 去 的 事 用 过 去 式 | — |
| mxlt | take1 | s1b1~4 | 5/5 | 英 文 式 的 is 背 的 | — |
| mxlt | take1 | s1b3~1 | 0/16 | 第 三 块 中 午 有 一 趟 开 往 多 伦 多 的 火 车 | — |
| mxlt | take1 | s1b3~2 | 2/34 | 开 往 多 伦 多 的 火 车 就 是 a train to toronto 火 车 中 午 才 开 这 是 站 在 过 去 说 将 来 所 以 用 relief | — |
| mxlt | take1 | s1b3~3 | 2/11 | 英 文 是 a train to toronto would live at no | — |
| mxlt | take1 | s1p2~1 | 4/12 | 得 分 点 二 a train to toronto 无 理 外 弄 | — |
| mxlt | take1 | s1p2~2 | 2/25 | 地 点 时 间 都 具 体 方 案 才 可 信 原 来 说 离 目 的 地 还 有 一 百 公 里 | — |
| mxlt | take1 | s1p2~3 | 1/24 | 这 一 句 就 把 怎 么 去 的 问 题 解 决 了 对 应 第 一 条 与 原 来 融 洽 | — |
| mxlt | take1 | s1h~1 | 1/9 | 这 句 话 还 有 别 的 写 吗 | — |
| mxlt | take1 | s1h~2 | 5/27 | 前 半 句 可 以 写 the nearest station 我 just show 的 微 微 最 近 的 车 站 开 车 一 会 儿 就 到 | — |
| mxlt | take1 | s1h~3 | 5/15 | 后 半 句 也 可 以 写 a train would be photo onto a no | — |
| mxlt | take2 | s1b1~1 | 0/8 | 怎 么 把 它 翻 成 英 文 | — |
| mxlt | take2 | s1b1~2 | 2/26 | 我 们 按 逗 号 把 中 文 切 成 几 小 块 一 块 一 块 的 分 最 后 再 连 成 一 句 | — |
| mxlt | take2 | s1b1~3 | 0/19 | 第 一 块 他 们 解 释 说 讲 的 是 过 去 的 事 用 过 去 式 | — |
| mxlt | take2 | s1b1~4 | 3/5 | 英 文 是 内 explain 的 | — |
| mxlt | take2 | s1b3~1 | 1/16 | 第 三 份 中 午 有 一 趟 开 往 多 伦 多 的 火 车 | — |
| mxlt | take2 | s1b3~2 | 2/34 | 开 往 多 伦 多 的 火 车 就 是 a train to toronto 火 车 中 午 才 开 这 是 站 在 过 去 说 将 来 所 以 will leave | — |
| mxlt | take2 | s1b3~3 | 5/11 | 英 文 是 a tune to toronto 物 理 原 known | — |
| mxlt | take2 | s1p2~1 | 3/12 | 得 分 点 二 a train to toronto would 例 外 no | — |
| mxlt | take2 | s1p2~2 | 1/25 | 地 点 时 间 都 具 体 方 案 才 可 行 原 文 说 离 目 的 地 还 有 一 百 英 里 | — |
| mxlt | take2 | s1p2~3 | 0/24 | 这 一 句 就 把 怎 么 去 的 问 题 解 决 了 对 应 第 一 条 与 原 文 融 洽 | — |
| mxlt | take2 | s1h~1 | 0/9 | 这 句 话 还 有 别 的 写 法 | — |
| mxlt | take2 | s1h~2 | 7/27 | 前 半 就 可 以 写 the near station was just 受 到 周 围 最 近 的 车 辆 开 车 一 会 儿 就 到 | — |
| mxlt | take2 | s1h~3 | 3/15 | 后 半 句 也 可 以 写 a train will leave for down on at noon | — |
| mxlt | take3 | s1b1~1 | 1/8 | 怎 么 把 它 分 成 英 文 | — |
| mxlt | take3 | s1b1~2 | 1/26 | 我 们 按 逗 号 把 中 文 切 成 几 小 块 一 块 一 块 的 翻 最 后 再 连 成 一 句 | — |
| mxlt | take3 | s1b1~3 | 0/19 | 第 一 块 他 们 解 释 说 讲 的 是 过 去 的 事 用 过 去 式 | — |
| mxlt | take3 | s1b1~4 | 3/5 | 英 文 是 the explain 的 | — |
| mxlt | take3 | s1b3~1 | 0/16 | 第 三 块 中 午 有 一 趟 开 往 多 伦 多 的 火 车 | — |
| mxlt | take3 | s1b3~2 | 2/34 | 开 往 多 伦 多 的 火 车 就 是 a train to toronto 火 车 中 午 才 开 这 是 站 在 过 去 说 将 来 所 以 我 leave | — |
| mxlt | take3 | s1b3~3 | 5/11 | 英 文 是 a train toronto 我 李 百 栋 | — |
| mxlt | take3 | s1p2~1 | 5/12 | 得 分 点 二 a train toronto will live the no | — |
| mxlt | take3 | s1p2~2 | 8/25 | 地 点 时 间 都 具 体 放 在 了 心 比 方 说 离 目 的 地 还 有 一 百 英 米 | — |
| mxlt | take3 | s1p2~3 | 0/24 | 这 一 句 就 把 怎 么 去 的 问 题 解 决 了 对 应 第 一 条 与 原 文 融 洽 | — |
| mxlt | take3 | s1h~1 | 0/9 | 这 句 话 还 有 别 的 写 法 | — |
| mxlt | take3 | s1h~2 | 6/27 | 前 面 句 可 以 写 的 nearest station 我 just short up 为 最 近 的 车 站 开 车 一 会 儿 就 到 | — |
| mxlt | take3 | s1h~3 | 4/15 | 后 半 句 也 可 以 写 a train would be for the on avenue | — |
