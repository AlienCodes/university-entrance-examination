# 高考阅读朗读程序（美式发音 · 男声 / 女声）

把 70 篇高考阅读 C、D 篇逐句合成为美式英语朗读音频，并生成逐句时间轴和中英双语字幕，可以直接用来做“上面英文、下面中文”的逐句视频。

- **引擎**：[Kokoro-82M](https://github.com/hexgrad/kokoro)（目前公认音质最好的开源英文语音模型之一）。在本机 CPU 上运行，不需要联网，不需要任何 API 密钥，也不收费。
- **发音**：[misaki](https://github.com/hexgrad/misaki) 美式英语词典 + 词性判断（区分 *produce* 名词/动词这类多音词）。人名、地名、多音词的修正放在 `pronunciations.json`，已经逐句审查过 70 篇。
- **文本规范化**（`textnorm.py`）：去掉中文注释；数字、年份、日期、百分比、货币、单位、分数一律转成美式读法（如 2011 → *twenty eleven*，£520m → *five hundred twenty million pounds*，March 7, 1907 → *March seventh, nineteen oh seven*）。
- **节奏与音质**：逐句合成，保留模型自然的句内语调；句间停顿随句长微调，段落之间停得更长；统一响度到 −16 LUFS（播客/视频常用标准），48 kHz 输出。

## 输出（仓库根目录 `audio/`）

```
audio/
  female/ p58_2026_全国Ⅰ卷_阅读C.mp3   女声音频
          p58_2026_全国Ⅰ卷_阅读C.srt   中英双语字幕（剪映、Premiere、PotPlayer 都能直接导入）
          p58_2026_全国Ⅰ卷_阅读C.vtt   网页用字幕
  male/   ……                           男声，文件名相同
  timings.json                         每篇每句的起止时间（秒），做视频时可用来逐句切画面
  qa_report.md                         自检报告
```

文件名开头的 `p01`～`p70` 就是网页里的顺序：按年份排，每年全国卷在前。

## 安装

需要 Python 3.10 及以上。

- **Windows**：双击 `setup_windows.bat`。
- **Mac / Linux**：`bash setup.sh`。

安装脚本会建立独立的虚拟环境 `.venv`，并从 GitHub 下载约 350 MB 的模型到 `models/`。

## 使用

以下命令都在 `tools/tts` 目录下运行。Windows 用 `.venv\Scripts\python`，Mac/Linux 用 `.venv/bin/python`。

```bash
python gaokao_tts.py passages                     # 生成全部 70 篇，男女声各一份
python gaokao_tts.py passages --only p58 p59      # 只生成指定文章
python gaokao_tts.py passages --voices male       # 只生成男声
python gaokao_tts.py passages --wav               # 另存无损 WAV，剪视频时用
python gaokao_tts.py say "Any English text you like." -o demo.mp3 --voice male
python gaokao_tts.py subs                         # 翻译更新后只重写字幕，不用重新合成
```

在 4 核 CPU 上，合成速度大约是音频时长的 1/3。一篇 2 分钟左右的文章约 40 秒生成；全部 70 篇男女声大约需要 2 小时。

## 调整声音

`voices.json` 定义了两个声音：

| 字段 | 含义 |
|---|---|
| `style` | 音色。可以是单个音色名（如 `af_heart`），也可以混合，如 `{"am_michael": 0.6, "am_fenrir": 0.4}` |
| `speed` | 语速，1.0 为正常。给初学者可以设 0.9 |
| `sentence_pause` / `paragraph_pause` | 句间、段间停顿（秒） |
| `lufs` | 响度 |

可选音色：女声 `af_heart af_bella af_sarah af_nova af_kore af_aoede af_jessica af_river af_alloy af_sky af_nicole`，男声 `am_michael am_fenrir am_puck am_echo am_eric am_liam am_onyx am_adam`。默认音色是用下面的自检工具在全部候选中客观比较后选出的。

## 修正发音

在 `pronunciations.json` 中添加修正：

```json
{
  "global":   { "Nice": "nˈis" },
  "sentence": { "p39:2": { "produce": "pɹˈOdus" } },
  "text":     { "p02:1": [["“a”", "“A”"]] }
}
```

- `global`：这个词在所有文章里都这样读，适合人名、地名。
- `sentence`：只在某篇某句里这样读，适合多音词。
- `text`：把某句的朗读文本里的一段换成另一段。

音素写法见 `tools/tts/PHONEMES.md`。改完后重新生成对应文章即可。

## 自检（可选）

```bash
bash setup.sh --qa          # 或 setup_windows.bat --qa；会额外安装 PyTorch，体积较大
python gaokao_tts.py qa     # 生成 audio/qa_report.md
```

自检会把每句音频切出来做两件事：

1. 用 Parakeet 语音识别模型把音频转回文字，和原文比对，找出可能读错的词。
2. 用 UTMOS 给每句的自然度打分。UTMOS 是自动预测的平均意见分，满分 5 分，真人有声书录音一般在 4.0～4.3 分。
