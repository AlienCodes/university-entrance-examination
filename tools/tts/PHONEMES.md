# 音素写法（misaki 美式英语）

`pronunciations.json` 里的发音用 misaki 的音素记号书写。

重音符号写在**重读元音的正前方**，不是写在音节开头：`ˈ` 表示主重音，`ˌ` 表示次重音。例如 nice 写作 `nˈIs`，provide 写作 `pɹəvˈId`。

## 双元音（用一个大写字母表示）

| 记号 | 国际音标 | 例词 |
|---|---|---|
| `A` | /eɪ/ | day |
| `I` | /aɪ/ | eye |
| `O` | /oʊ/ | go |
| `W` | /aʊ/ | how |
| `Y` | /ɔɪ/ | boy |

## 单元音

| 记号 | 例词 |
|---|---|
| `i` | see |
| `ɪ` | sit |
| `ɛ` | bed |
| `æ` | cat |
| `ɑ` | father, cot |
| `ɔ` | law；与 ɹ 连用写 `ɔɹ`，如 or |
| `ʌ` | cup |
| `ʊ` | book |
| `u` | food |
| `ə` | 弱读 schwa |
| `ɜɹ` | bird |
| `əɹ` | butter |
| `ɐ` | 冠词 a 的弱读 |
| `ᵊ` | 极短的 schwa，如 level `lˈɛvᵊl` |
| `ᵻ` | 介于 ə 和 ɪ 之间，如复数词尾 -es |

## 辅音

- 一般辅音：`p b t d k ɡ f v θ ð s z ʃ ʒ h m n ŋ l ɹ j w`
- `ʧ`：church
- `ʤ`：judge
- `T`：美式闪音，如 city `sˈɪTi`
- `ʔ`：喉塞音

## 注意

- 用 `ɡ`（U+0261），不要用英文字母 g。
- 用 `ɹ` 表示 r。
- 不要用 `ː ɚ ɝ oʊ eɪ aɪ aʊ ɔɪ`，分别改用 `əɹ`、`ɜɹ` 和上面的大写字母。

## 试听某个写法

```bash
python gaokao_tts.py say "[Nice](/nˈis/) is a city in France." -o test.mp3
```
