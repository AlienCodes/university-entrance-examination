# 逐句朗读视频

把一篇文章做成 16:9 的逐句精读视频。默认分辨率 3840×2160（4K），也可以输出 1080p。

视频结构：

1. **片头**：显示年份、试卷、阅读 C/D 篇和文章标题，静音 1.5 秒。
2. **正文**：一句一屏，依次是英文原文（生词按三种颜色高亮）、中文翻译、本句生词表。
3. **同步**：声音与画面按 `audio/timings.json` 逐句同步，在两句之间的停顿处切换画面。
4. **结尾**：读完最后一句后，画面停留并保持 2 秒静音；生成后程序会实测确认，不足 2 秒就报错。

## 用法

```bash
# 先生成该篇音频（tools/tts）和网页数据（tools/build.py），再运行：
python make_video.py p58                 # 女声，4K
python make_video.py p58 --voice male    # 男声
python make_video.py p58 --scale 1       # 1920×1080
```

成品输出到仓库根目录的 `最终视频/` 文件夹，文件名和片头一致：`年份 试卷 阅读C/D 题目.mp4`，例如 `2026 全国Ⅰ卷 阅读C 纽约大规模种树的“隐患”.mp4`。

## 依赖

- 在 tools/tts 的虚拟环境里安装 `playwright`（`pip install playwright`，然后运行 `playwright install chromium`）。
- 需要 `ffmpeg`。

字体放在 `fonts/`：思源黑体 Noto Sans SC 和 Source Serif 4，均采用 SIL Open Font License。
