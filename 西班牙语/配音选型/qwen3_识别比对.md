# 语音识别回转比对：Qwen3 成品 与 Supertonic 样音（es01，2026-10-15）

Qwen3-TTS 是大语言模型式的合成，可能跳词、重复、读错；画面上的西语和朗读不一致就是错误视频。所以成品 MP3 逐句送进语音识别，
和原文逐词比较，每一处差异都逐个查清是“识别器听错”还是“合成真读错”。

## 怎么做的

- 识别模型：sherpa-onnx 的 NeMo Parakeet TDT 0.6B v3（多语种，含西班牙语，int8），和合成模型完全无关（独立测量）。
- 命令：`/opt/es_tts_envs/sherpa/bin/python 西班牙语/tools/qa_asr.py es01 成品.mp3 --model 识别模型文件夹`
  （按 ≥ 0.6 秒静音切句，切出的句数必须等于原文句数；比较时忽略大小写、标点，重音符号单列）。
- 每一处差异再做两步核对：
  1. **单独识别**：只把这几个词附近的一小段音频（约 0.5–1.3 秒）送进识别。整句识别时识别器会按上下文“猜”，把两个词并成一个；
     单独识别时如果原词清清楚楚地出来，就说明声音里有这个词，是识别器听错。
  2. **声学核对**（单独识别也拿不准时）：看音高、能量和高频擦音，例如重音落在哪个音节、j 的清擦音还在不在。

## 结论

| 音频 | 句数 / 词数 | 逐词差异 | 识别器听错 | 合成真读错 |
|---|---|---|---|---|
| **成品 Qwen3 克隆 M1F5_25（种子 1234）** | 9 / 109 | 2 处 | 2 处 | **0 处** |
| 样音 2_高一些（Supertonic M1F5_25） | 9 / 109 | 4 处 | 2 处 | **1 处**（第 7 句 viajar 吞掉 j），另 1 处拿不准 |
| 样音 0_原声M1（Supertonic M1） | 9 / 109 | 6 处 | 4 处 | 1 处（同上 viajar），另 1 处拿不准 |
| 样音 1_稍高（Supertonic M1F3_25） | 9 / 109 | 2 处 | 0 处 | 1 处（同上 viajar），另 1 处拿不准 |
| 样音 3_再高一些（Supertonic M1F5_30） | 9 / 109 | 4 处 | 2 处 | 1 处（同上 viajar），另 1 处拿不准 |

**Qwen3 成品没有漏读、多读、读错的词**，可以作为最终配音。Supertonic 四个样音在第 7 句 “Prefiero viajar” 都把 j 吞掉
（识别器分别听成 vir / viar / via），这是 Supertonic 的一个真实缺陷（它每次合成都带随机性，但这里四个音色都一样）。

## Qwen3 成品逐句（西班牙语/audio/qwen3_M1F5_25/es01_Mi_pasion_por_los_viajes.mp3）

| 句 | 原文 | 识别结果（整句） | 差异 | 判定 |
|---|---|---|---|---|
| 1 | Tengo una gran pasión por los viajes. | Tengo una gran pasión por los viajes. | 无 | 一致 |
| 2 | Me encanta conocer lugares nuevos, culturas diferentes y probar comidas típicas de cada región. | Me encanta conocer lugares nuevos, culturales y probar comidas típicas de cada región. | culturas diferentes → culturales | **识别器听错**：单独识别 6.55–7.80 秒得到 “Culturas diferentes”，只取 7.2–7.8 秒得到 “diferentes”；整句识别里 “cultur…” 到 “…ales” 跨了约 1 秒，正是两个词的长度 |
| 3 | Cada vez que visito una ciudad distinta, aprendo cosas nuevas y amplío mi visión del mundo. | … aprendo cosas nuevas y amplí mi visión del mundo. | amplío → amplí | **识别器听错**：单独识别 14.9–15.8 秒得到 “y amplio mi”（词尾 o 在）；声学核对重音：am 音高约 110–121 Hz，plí 跳到 195 Hz、元音拖长约 0.3 秒，重音在 í 上，是动词 amplío 的正确读法 |
| 4 | Me gusta viajar por España, conocer sus pueblos pequeños, playas y montañas. | Me gusta viajar por España. Conocer sus pueblos pequeños, playas y montañas. | 无（只差标点） | 一致 |
| 5 | También deseo visitar otros países de Europa en el futuro. | 同原文 | 无 | 一致 |
| 6 | Me fastidia el turismo masivo que daña los lugares históricos. | 同原文 | 无 | 一致 |
| 7 | Prefiero viajar tranquilo, sin prisa, observar la vida local y hablar con la gente del lugar. | 同原文 | 无 | 一致 |
| 8 | Los viajes me hacen más abierto y me enseñan a valorar la diversidad del planeta. | 同原文 | 无 | 一致 |
| 9 | Es una experiencia que nunca quiero dejar de vivir. | 同原文 | 无 | 一致 |

13 个合成片段全部用种子 1234 一次合成成功（时长自检没有触发换种子重试）。

## 对比：Supertonic M1F5_25 样音逐句（配音选型/样音_2026-10-15/2_高一些.mp3）

| 句 | 原文 | 识别结果（整句） | 差异 | 判定 |
|---|---|---|---|---|
| 1 | Tengo una gran pasión por los viajes. | 同原文 | 无 | 一致 |
| 2 | Me encanta conocer lugares nuevos, culturas diferentes y probar comidas típicas de cada región. | … lugares nuevos, culturentes y probar … | culturas diferentes → culturentes | 识别器听错：单独识别 6.85–8.1 秒得到 “Culturas diferentes” |
| 3 | Cada vez que visito una ciudad distinta, aprendo cosas nuevas y amplío mi visión del mundo. | … y amplí mi visión del mundo. | amplío → amplí | 识别器听错：单独识别得到 “y amplio mi visión” |
| 4 | Me gusta viajar por España, conocer sus pueblos pequeños, playas y montañas. | 同原文（只差标点） | 无 | 一致 |
| 5 | También deseo visitar otros países de Europa en el futuro. | 同原文 | 无 | 一致 |
| 6 | Me fastidia el turismo masivo que daña los lugares históricos. | 同原文 | 无 | 一致 |
| 7 | Prefiero viajar tranquilo, sin prisa, observar la vida local y hablar con la gente del lugar. | Prefiero VIR Tranquilo. Semprisa. Observar … | viajar → vir；sin prisa → semprisa | viajar：**合成真读错（吞音）**。单独识别 33.85–34.5 秒仍是 “VIR”；声学核对：同一个样音第 4 句的 viajar 在 a 和 ar 之间有约 60–80 毫秒清擦音（j），第 7 句这里只有约 40 毫秒的浊音弱化，没有清擦音，j 基本被吞掉。sin prisa：**拿不准**，单独识别得到 “Simpresa”；n 在 p 前读成 m 是西语正常连读，元音 i 是否读得不够清楚，靠识别判断不了 |
| 8 | Los viajes me hacen más abierto y me enseñan a valorar la diversidad del planeta. | 同原文 | 无 | 一致 |
| 9 | Es una experiencia que nunca quiero dejar de vivir. | 同原文 | 无 | 一致 |

其余三个 Supertonic 样音（整句识别的差异 → 核对结果）：

- 0_原声M1：culturas diferentes → culturales、amplío → amplí（同上，识别器听错）；playas → play（放宽窗口单独识别得到 “playas”，识别器听错）；
  daña → daños（单独识别得到 “que daña los lugares”，识别器听错：daña los 连读）；viajar → vir（同 2_高一些，吞音）；sin prisa → semprisa（拿不准）。
- 1_稍高：viajar → viar（吞音，同上）；sin → sem（拿不准）。其余 7 句完全一致。
- 3_再高一些：culturas diferentes → culturentes（识别器听错，同上）；daña los → daños（单独识别得到 “que daña los lugares”，识别器听错）；
  viajar → via（吞音，同上）；sin prisa → semprisa（拿不准）。

## 复现

识别模型下载（约 490 MB，用完可删）：
`https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8.tar.bz2`
