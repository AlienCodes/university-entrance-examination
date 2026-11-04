# 交接：老师 GPT-SoVITS 专属模型配音（2026-11-04）

上一会话：session_01BA1TPE2uvs3qyQoi5kxSnt（对话超 4 MB 换新会话）。协调会话 session_01Bo2nvX3EdvyJhDdDqVayNH，结果都用 send_message 发它。

## 现状（已做通）
- 工作流 `.github/workflows/tts-sovits.yml`：workflow_dispatch（task = `高考语法填空/tts/` 下的任务文件名，model_url = 老师模型 zip 的云盘链接，协调会话有；老师说这是公共资源，可以公开）。
  fetch 任务用 HTTP Range 远程读 19.35 GB 的 zip，只取 models.json 选中的权重（vt_433bc0_e24_s5976.pth + vt_433bc0-e8.ckpt）和 VoiceTwin 参考（中文 3 条），约 1 分钟，传 artifact `sovits-model`；
  合成分片（`高考语法填空/tools/sovits_synth.py`，GPT-SoVITS abe9843，CPU）与 Qwen 同一任务格式、同一输出结构；结果在分支 gram-tts-out 的 `runs/<任务>-<运行号>/`（运行 #12 以前是 `-sovits-<号>`，合成完整性.py 认不出任务清单，已改）。
- 候选写法：`{"id": "g1", "mode": "gptsovits", "weights": "teacher", "split": "mark", "gap_max": 0.45}`；可选 `gen`（全部小段的采样参数）、`gen_en`（只英文小段，现用 `{"top_k": 10, "temperature": 0.8}`）、`ref_free_en`、`voice`（换参考）、`en_ref: tx`（老师英文切片：transcripts.csv 1008 条全是中文，做不了）。
- 定下的：声音用 g1（老师模型 + VoiceTwin 参考）；不用 mark+word（单词单独合成一顿一顿、拼接 6/6 不过）；英文段用 g1lt 采样参数（英文专项 whisper 词错率 0.11—0.18 对 0.23—0.30）。
- 量法：`高考续写/tools/声音对比.py`（完整处理链 + 全部检查、基频、相似度、SenseVoice / parakeet / whisper 识别、中文段里夹的英文按对齐截出再认）。本机评测环境：`/opt/ttsenv`（python3 -m venv；pip 装 sherpa-onnx numpy scipy soundfile soxr librosa pyloudnorm lameenc num2words jieba pypinyin pyyaml；torch 用 `uv pip install --no-cache -p /opt/ttsenv/bin/python torch torchaudio`（PyPI CUDA 版，CPU 能用））；模型 `tools/tts/download_models.py --qa` + sherpa-onnx 发布页的 sense-voice、3dspeaker_eres2net_base_zh_16k.onnx、whisper-base.en；老师真声 Release user-voice 的 05.wav。

## 进行中 / 按顺序要做的
1. **v3 讲法样段**（讲稿会话 session_01BA1TPGPHbHJpqwMLt2R4fj 要的 14 段）：上一会话在本机链里做（主合成运行 #10 + 补 s1p2 / s1e / s1z2，选段），成品名 `高考续写/预览/2026 新课标Ⅰ卷 读后续写 讲解 样段 v3 讲法（老师模型 g1）.mp3`。若已推送，看协调会话是否已收到；若没推，新会话重做：
   ```
   取 gram-tts-out 的 runs/任务_续写_样段v3_sovits-sovits-10 → 本机改名为 任务_续写_样段v3_sovits-10（让合成完整性认出任务）；
   删掉 g1/take*/ 里 s1z、s1e、s1p2 的旧小段（s1z.wav、s1z~*.wav …），删掉空的 take 目录；
   bash 高考续写/tools/覆盖补合成.sh <g1 目录> g1 任务_续写_样段v3_sovits_补s1p2.json 0（再 补s1e、补s1z2 各一次）；
   /opt/ttsenv/bin/python 高考语法填空/tools/选段.py --稿 高考续写/讲解/2026_新课标Ⅰ卷/稿.json --run <g1 目录> --out "<成品名>" --拆分 mark --停顿上限 0.45 --only t01 t02 t03 t04 s1z s1b1 s1b2 s1b3 s1bj s1bf s1e s1p1 s1p2 s1h
   ```
2. **夹英文对比（已做完，2026-11-04）**：运行 #17（s1b1 s1b3 s1h s1p2，各 3 次），3 次平均：mx1 检查通过 3/3、相似度 0.911、SenseVoice 0.159、夹英文错词率 parakeet 0.707 / whisper 0.447；mxlt 1/3（另 2 次拼接语速差 1.41、1.46 倍不过）、0.915、0.133、0.577 / 0.464。两个识别器结论相反、mxlt 拼接变差 → **保持现状**：整片中文段不加 `gen`，只英文段 `gen_en`。报告与两份“每句最好”MP3（带合格证）在 `高考续写/预览/声音对比/任务_sovits_夹英文-17_*`。
3. 整片：新稿 + 英文做法定了、老师听过样段点头后才合成一次（`任务_续写_全片_sovits.json` 照新结论改，parts 10 × takes 3，并行 20）；选段、出视频交给 v2 会话的 `续写全片.sh`（VOICE=g1，不带旧 Qwen 的 OVERLAY_TASK / DROP_TASK / LOCK / KEEP_ORIG / SYNTH_ALLOW_MISSING）。

## 要用户 / 协调会话定的
- 英文要更像 native：老师的素材里没有纯英文切片，最有效的是请老师录 2—3 句 5—8 秒的纯英文当英文参考（协调会话在问老师）；后备：英文用母语合成后做声音转换（先不做）。
- 防复发登记已补：踩坑 113（`仓库检查.gram_out_problems`：推 gram-tts-out 的工作流结果目录必须是 runs/<任务>-<运行号>；双向验证 `python3 tools/防复发/验证/仓库检查.py`）。

## 清晰度（2026-11-04，会话 session_01BA1TPCZHz3z6JQ1NDG4iK8）
- 老师听 v3：“很多发音都没有发清楚”。程序量出：根子在合成（温度 1.0 单抽含糊、SoVITS 输出低频多高频少），处理链不是主因。报告 `高考续写/预览/声音对比/清晰度_v3对v4_报告.md`。
- **新默认**：候选加 `"gen": {"temperature": 0.6, "top_p": 0.8}`（lt6），每小段 6 次；选段加 `--音色还原 '[[60,500,-2.5],[5000,9000,2.0]]'`（续写全片.sh 用环境变量 `TIMBRE=...`）；选段中文段两个识别器（SenseVoice + Paraformer）一起计分。`任务_续写_全片_sovits.json` 已改（takes 1—6，候选 id 仍是 g1）。
- **v4 样段**：`高考续写/预览/2026 新课标Ⅰ卷 读后续写 讲解 样段 v4（老师模型，清晰）.mp3`（识别错误率 SenseVoice 0.048→0.021、Paraformer 0.082→0.040；4 kHz 以上 0.024→0.050；擦音 −7.6→−4.4 dB；真声 0.019 / 0.020、0.035—0.042、−5.8—−4.3）。音色还原是新处理：等老师听过点头再用于整片（铁律 10④）。
- **新关口**（踩坑 115）：`tools/tts/清晰度.check`，`讲解音频.render` 每次跑；双向验证 `/opt/ttsenv/bin/python tools/防复发/验证/清晰度.py`。本机要 `tools/tts/models/sherpa-onnx-paraformer-zh-2024-03-09`（sherpa-onnx 发布页 asr-models，只留 model.int8.onnx）。
- 工作流新增：`sovits_synth` 候选可写 `aux`（辅助参考条数）、`ref_pick`（第几条当主参考）；fetch 时 `取模型.py` 挑 30 条真声中文切片到 tx/，`baseline` 作业量真声识别错误率，结果 `runs/<任务>-<号>/真声基准.json`（只有数字）。
- 本机容器拿不到云盘（代理 403）和 artifact 下载（403），真声切片只能在 Actions 上量。本机盘配额小：clone 11 GB，识别模型只留 int8。
- 没解决：基频仍低约 1.1 个半音（101.5 对 107.9 Hz）；夹英文错词率没变（parakeet 0.54、whisper 0.45）。
