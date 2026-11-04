# 声音对比（GPT-SoVITS 专属模型）

运行：`任务_sovits_英文专项-sovits-9`；8 句（s1e s2e s3e s4e s5e s9e s10e s11e）；真声：05.wav
真声对照：相似度（真声两段之间）0.827；真声浊音基频中位数 112.5 Hz（协调会话给的 106.2 Hz）

| 候选 | 次 | 处理链与全部检查 | 基频 Hz | 与真声差（半音） | 与 106.2 Hz 差 | 相似度 | 英文部分相似度 | 识别错误率（SenseVoice） | 英文词错率（parakeet） | 英文词错率（whisper） |
|---|---|---|---|---|---|---|---|---|---|---|
| g1 | take1 | 全部通过 | 98.2 | -2.35 | -1.35 | 0.903 | 0.901 | 0.178 | 0.062 | 0.302 |
| g1 | take2 | 全部通过 | 96.3 | -2.70 | -1.70 | 0.896 | 0.896 | 0.194 | 0.085 | 0.233 |
| g1 | take3 | 全部通过 | 97.7 | -2.45 | -1.45 | 0.897 | 0.895 | 0.178 | 0.101 | 0.225 |
| g1lt | take1 | 全部通过 | 98.0 | -2.40 | -1.40 | 0.898 | 0.898 | 0.116 | 0.078 | 0.109 |
| g1lt | take2 | 全部通过 | 98.0 | -2.40 | -1.40 | 0.892 | 0.890 | 0.132 | 0.047 | 0.147 |
| g1lt | take3 | 全部通过 | 96.0 | -2.75 | -1.75 | 0.893 | 0.895 | 0.194 | 0.116 | 0.178 |
| g1rf | take1 | 全部通过 | 96.3 | -2.70 | -1.70 | 0.896 | 0.899 | 0.140 | 0.093 | 0.264 |
| g1rf | take2 | 全部通过 | 95.7 | -2.80 | -1.80 | 0.889 | 0.890 | 0.186 | 0.078 | 0.209 |
| g1rf | take3 | 全部通过 | 96.8 | -2.60 | -1.60 | 0.891 | 0.891 | 0.147 | 0.085 | 0.217 |

## 每个候选每句最好的一次拼成一份

| 候选 | 处理链与全部检查 | MP3 | 每句用的是哪一次 |
|---|---|---|---|
| g1 | 全部通过 | 任务_sovits_英文专项-sovits-9_g1_每句最好.mp3 | s1e:3 s2e:2 s3e:3 s4e:1 s5e:2 s9e:2 s10e:1 s11e:1 |
| g1lt | 全部通过 | 任务_sovits_英文专项-sovits-9_g1lt_每句最好.mp3 | s1e:1 s2e:1 s3e:2 s4e:1 s5e:2 s9e:1 s10e:1 s11e:1 |
| g1rf | 全部通过 | 任务_sovits_英文专项-sovits-9_g1rf_每句最好.mp3 | s1e:1 s2e:1 s3e:2 s4e:1 s5e:1 s9e:1 s10e:1 s11e:3 |

## 每个小段的识别

| 候选 | 次 | 小段 | 错 / 字词数 | SenseVoice 识别 | parakeet 错词 |
|---|---|---|---|---|---|
| g1 | take1 | s1e | 4/16 | there was a station nearby they explained that a train to toronto with leave wei don | 3 |
| g1 | take1 | s2e | 3/8 | but what about my car m and s anxiously | 1 |
| g1 | take1 | s3e | 8/18 | daniel promised the habit told out of the kept in his corrosion till she returned | 1 |
| g1 | take1 | s4e | 0/16 | the couple then drove her to the station and waited with her until the train arrived | 0 |
| g1 | take1 | s5e | 2/15 | waving to them through the first train window emily could hardly hold back her ears | 1 |
| g1 | take1 | s9e | 4/19 | emily handed them a box home made cookies and a car that red thank you for saving my holiday | 0 |
| g1 | take1 | s10e | 0/14 | we just did what anyone would do rachel said giving her a warm hug | 2 |
| g1 | take1 | s11e | 2/23 | driving away emily realized that the stone had nearly ruined her christmas but two strangers had made it the womans of her life | 0 |
| g1 | take2 | s1e | 5/16 | there was a station nearby they explained and the train totor onto would leave aton | 2 |
| g1 | take2 | s2e | 0/8 | but what about my car emily asked anxiously | 0 |
| g1 | take2 | s3e | 12/18 | daniel promised having told our audit kept his gr she returned | 4 |
| g1 | take2 | s4e | 0/16 | the couple then drove her to the station and waited with her until the train arrived | 0 |
| g1 | take2 | s5e | 1/15 | waving to them through the frosty train window emily could hardly hold back her ears | 1 |
| g1 | take2 | s9e | 3/19 | emily handed them a box home made cookies and a car that read thank you for saving my holiday | 0 |
| g1 | take2 | s10e | 0/14 | we just did what anyone would do rachel said giving her a warm hug | 2 |
| g1 | take2 | s11e | 4/23 | driving away emily realized that this stone had nearly ruined her chtma but two strangers admitted made it the warmest of her life | 2 |
| g1 | take3 | s1e | 6/16 | there was a station nearby they explained and train the toronto were legal the no | 0 |
| g1 | take3 | s2e | 1/8 | what about my car emily asked anxiously | 1 |
| g1 | take3 | s3e | 7/18 | daniel promised he to out of the kitchen kept his garage until she returned | 1 |
| g1 | take3 | s4e | 0/16 | the couple then drove her to the station and waited with her until the train arrived | 1 |
| g1 | take3 | s5e | 2/15 | weaving to them through the frosty train window emily could hardly hold back her ears | 3 |
| g1 | take3 | s9e | 4/19 | ammy handed them a box of home made cookies and a car that read thank you for saving my holiday | 2 |
| g1 | take3 | s10e | 0/14 | we just did what anyone would do rachel said giving her a warm hug | 2 |
| g1 | take3 | s11e | 3/23 | the timinging away emily realized that the storm had nearly ruined her christmas but the two strangers had made it the warmest of her life | 3 |
| g1lt | take1 | s1e | 1/16 | there was a station nearby they explained and a train to toronto would leave at no | 1 |
| g1lt | take1 | s2e | 0/8 | but what about my car emily asked anxiously | 0 |
| g1lt | take1 | s3e | 8/18 | daniel promised the heavy to out the kept in his garage till she returned | 5 |
| g1lt | take1 | s4e | 0/16 | the couple then drove her to the station and waited with her until the train arrived | 0 |
| g1lt | take1 | s5e | 1/15 | waving to them through the frosty train window emily could hardly hold back her ears | 2 |
| g1lt | take1 | s9e | 4/19 | emily handed them a box of home made cookies and a car that red thank you for saving my holiday | 0 |
| g1lt | take1 | s10e | 0/14 | we just did what anyone would do rachel said giving her a warm hug | 2 |
| g1lt | take1 | s11e | 1/23 | driving away emily realized that the storm had nearly ruin her christmas but two strangers had made it the warmest of her life | 0 |
| g1lt | take2 | s1e | 1/16 | there was a station nearby they explained that and a train to toronto would leave at noon | 1 |
| g1lt | take2 | s2e | 0/8 | but what about my car emily asked anxiously | 0 |
| g1lt | take2 | s3e | 7/18 | daniel pump the habit to out of the dish kept in his garage until she returned | 1 |
| g1lt | take2 | s4e | 0/16 | the couple then drove her to the station and waited with her until the train arrived | 0 |
| g1lt | take2 | s5e | 2/15 | waving to them through the frostty train window emily could hardly hold back her ears | 0 |
| g1lt | take2 | s9e | 6/19 | emily handed them a box of home made cookies and coronary thank you for saving my holiday | 1 |
| g1lt | take2 | s10e | 0/14 | we just did what anyone would do rachel said giving her a warm hug | 2 |
| g1lt | take2 | s11e | 1/23 | driving away emily realized that this storm had nearly ruined her christmas but two strangers had made it the warmest of her life | 1 |
| g1lt | take3 | s1e | 1/16 | there was a station nearby they explained and the train to toronto would leave at noon | 1 |
| g1lt | take3 | s2e | 4/8 | but what about my car m a s agency | 4 |
| g1lt | take3 | s3e | 9/18 | daniel promised the he to al of the d kept in his corrosion till she returned | 4 |
| g1lt | take3 | s4e | 0/16 | the couple then drove her to the station and waited with her until the train arrived | 0 |
| g1lt | take3 | s5e | 2/15 | laving to them through the frosty train window emily could hardly hold back her ears | 1 |
| g1lt | take3 | s9e | 7/19 | i may handed them a box of home made cookies and a car ni bread thank you for saving my holiday | 1 |
| g1lt | take3 | s10e | 1/14 | we just said what anyone would do rachel said giving her a warm hug | 3 |
| g1lt | take3 | s11e | 1/23 | driving away emmy realized that the storm had nearly ruined her christmas but two strangers had made it the warmest of her life | 1 |
| g1rf | take1 | s1e | 0/16 | there was a station nearby they explained and a train to toronto would leave at noon | 0 |
| g1rf | take1 | s2e | 2/8 | but what about my car emily asked the interesting | 0 |
| g1rf | take1 | s3e | 8/18 | daniel promised the habit told al the dham kept in his garage until she returned | 6 |
| g1rf | take1 | s4e | 0/16 | the couple then drove her to the station and waited with her until the train arrived | 0 |
| g1rf | take1 | s5e | 1/15 | waving to them through the frosty train window emily could hardly hold back her ears | 1 |
| g1rf | take1 | s9e | 3/19 | emily handed them a box of home made cookies and a car that read thank you for saving my holiday | 0 |
| g1rf | take1 | s10e | 0/14 | we just did what anyone would do rachel said giving her a warm hug | 2 |
| g1rf | take1 | s11e | 4/23 | driving away emily realized that the stone had nearly ruined her christmas but two strangers had mediated the worst of her life | 3 |
| g1rf | take2 | s1e | 0/16 | there was a station nearby they explained and a train to toronto would leave at noon | 0 |
| g1rf | take2 | s2e | 2/8 | th what about my car any asked anxiously | 1 |
| g1rf | take2 | s3e | 7/18 | dniiel promised the heavy to out of the edition kept in his garage until she returned | 0 |
| g1rf | take2 | s4e | 0/16 | the couple then drove her to the station and waited with her until the train arrived | 0 |
| g1rf | take2 | s5e | 3/15 | waving to them through the frosty train window an lee could hardly hold back her ears | 0 |
| g1rf | take2 | s9e | 8/19 | am may handed them a box of home made cookies and car and red thank you for saving my holiday | 4 |
| g1rf | take2 | s10e | 0/14 | we just did what anyone would do rachel said giving her a warm hug | 2 |
| g1rf | take2 | s11e | 4/23 | doughke away emily realized that the stone had nearly ruined her christ eyes but two strangers had made it the warmest of her life | 3 |
| g1rf | take3 | s1e | 1/16 | there was a station nearby they explained and the train to toronto would leave at noon | 1 |
| g1rf | take3 | s2e | 1/8 | but what about my car emmy asked anxiously | 1 |
| g1rf | take3 | s3e | 6/18 | daniel promised a having told out of the di kept in his garage until she returned | 1 |
| g1rf | take3 | s4e | 0/16 | the couple then drove her to the station and waited with her until the train arrived | 0 |
| g1rf | take3 | s5e | 5/15 | waving to them through the fusy train window and they could hardly hold back hard ears | 2 |
| g1rf | take3 | s9e | 2/19 | emily handed them a box of home made cookies and a card that read thank you for saving my holiday | 2 |
| g1rf | take3 | s10e | 1/14 | we just did what anyone wrote do rachel said giving her a warm hug | 2 |
| g1rf | take3 | s11e | 3/23 | drny a emily realized that the storm had nearly ruined her christmas but two strangers had made it the worst of her life | 2 |
