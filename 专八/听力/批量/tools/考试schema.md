# 批量专八考试视频数据接口

适配器：`考试视频.py`。复用 `专八/听力/tools/听力视频.py` 的2025白底黑字CSS、原卷字体、4K/30fps编码及原音核验，不修改2025引擎。新项目遵守更晚的铁律25：原声不增益、不限幅、不重采样、不改声道；用户本轮只授权剪去正式说明前的片头音乐。正式说明、题目、重复朗读、预览和答题停顿保留。

## 每年文件

年度目录包含UTF-8 `试卷.json` 和 `时间轴.json`。制作人员须先按原卷及原音核对。`answer:null`或空白答案可作为整理阶段的占位，但会被制作门禁拒绝，不能把待核答案当成成品。选择题题干未印出时，`stem`可暂用空字符串，画面会明确提示听录音题目，不伪造题干。

```json
{
  "year": 2009,
  "title": "2009年 专八听力 考试",
  "filename": "2009年 专八听力 考试.mp4",
  "minutes": 30,
  "sections": [
    {"id":"A","title":"SECTION A　MINI-LECTURE","lines":["Original instruction sentence."]},
    {"id":"B","title":"SECTION B　INTERVIEW","lines":["Original instruction sentence."]}
  ],
  "sheet":[
    ["title","Actual lecture title"],
    ["h","A heading"],
    ["b","a fact with {1}"],
    ["col"],
    ["b","another fact with {2}"]
  ],
  "gap_answers":["first answer","second answer"],
  "questions":[
    {"n":1,"stem":"An actual question?","options":["Option A.","Option B.","Option C.","Option D."],"answer":"A","group":"interview"}
  ],
  "groups":[
    {"id":"interview","title":"SECTION B　INTERVIEW","intro":"Actual instruction; may be omitted.","questions":[1]}
  ]
}
```

- `minutes`按原卷，勿统一假定25/30。文件名只给文件名，不允许路径。
- `sections`说明按原音实际区分，旧题型可有A/B/C等多个section；id自由但须唯一。
- `sheet`沿用2025双栏表达：`title`标题；`h`加粗小标题；`b`圆点条目；`e`进一步缩进例子；`d`破折号条目；`p`普通行；`col`换栏。内容不含HTML，空号用`{n}`，从1起连续，每空只出现一次。
- 如答题卡确实需要多页，写`sheets`为若干`sheet`数组并用事件`page:0/1`选页；不要同时依赖默认单页。每年的空数按真实材料，不假定全部10或15。
- `gap_answers`与卡片空号一一对应；同空多个可接受答案可写`answer1 / answer2`，中文括注`（任选三点）`另行排成小字。
- `questions`按题号，options顺序永远A/B/C/D，不带字母前缀。answer仅接受A/B/C/D。组内题号不要求从1连续，各组不得重复覆盖同一题。
- 印本与实际录音自身存在不可成立的题目时，可给该题 `unscored:true,source_note:"具体且简短的源题冲突说明"`。`answer`保留原资料A—D仅供来源比较，不视作已证实正确答案；单题页显示“题源表述存疑，本题不计分”，答案页用“—”及“题源存疑·不计分”代替正确选项，并保留简注。时间轴及成品核查报告均排除此题的有效计分数。
- `groups`只定义原音中实际题组，不能把不相关采访/新闻混成一组。选项预览一屏最多5题；大组用事件`numbers:[1,2,3,4,5]`选择子集并编排实际换页时间。
- 默认填空答案一屏最多16空、选择题答案一屏最多10题。旧题型若20题则自动分两屏，每屏25秒。若长答案需更宽松，可显式用`gap_answer_pages:[[1,...,8],[9,...]]`、`choice_answer_pages:[[1,...,10],[11,...]]`；须覆盖所有题号且不重复。填空每屏40秒，选择每屏25秒。

## 时间轴

所有时刻一律是**剪头前原音秒数**；ASR、剪音乐记录和此文件使用同一个时间基准。渲染器统一减去`trim.start`，不需调用方二次平移。

```json
{
  "source_duration": 1700.125,
  "source_sha256": "64位小写SHA256",
  "trim": {
    "start": 8.25,
    "reason": "片头音乐",
    "source_sha256": "64位小写SHA256",
    "evidence": "实际核定的音乐结束和第一句正式说明开口，保留开口前安全余量。"
  },
  "events":[
    {"t":8.25,"kind":"instr","sec":"A","hi":-1},
    {"t":10.0,"kind":"instr","sec":"A","hi":0},
    {"t":30.0,"kind":"sheet","st":"预览答题卡","countdown":{"end":60.0,"label":"预览"}},
    {"t":60.0,"kind":"sheet","st":"Mini-lecture 播放中，只放一遍"},
    {"t":800.0,"kind":"plist","group":"interview","st":"采访播放中"},
    {"t":1000.0,"kind":"q","n":1,"st":"念题"},
    {"t":1005.0,"kind":"q","n":1,"st":"请在答题纸上作答","countdown":{"end":1015.0,"label":"作答"}},
    {"t":1695.0,"kind":"end"}
  ]
}
```

上例只演示字段，不是真实2009年材料，不可拿示例时刻制作。events须按原音时间排序且不早于剪点、不超出原音。每题至少一个`q`事件；每个倒计时不能越过下一事件。不能在events中传入答案类型，答案由程序在完整录音结束后自动追加。

- 无音乐无需剪头：`trim:{"start":0}`，顶层`source_sha256`仍须绑定原音。
- 有剪头：reason仅接受`片头音乐`/`intro_music`，须写SHA与evidence。renderer不会自行推测剪点，也不接受删说明、删尾音、改速度等处理。
- `instr`按sec显示说明，hi从0起高亮指定句；-1不高亮。若说明过长需分屏，可在事件给`lines`子集，hi对应显示的子集；仍由制作者保证原说明完整覆盖。
- `sheet`可给page（从0起）；`plist`给group，长组可额外给numbers子集；`q`给n；所有画面可给简短中文st。
- 同一帧的说明/倒计时边界合并取最后状态，并写入核验记录；若两个不同题号撞到同帧直接拒绝。最终每一状态必须大于0帧。

## 命令

```bash
python 专八/听力/批量/tools/考试视频.py --自检
python 专八/听力/批量/tools/考试视频.py --convert-2025 /tmp/tem8-2025-schema
python 专八/听力/批量/tools/考试视频.py YEAR_DIR schema --out OUT
python 专八/听力/批量/tools/考试视频.py YEAR_DIR layout --sample --out OUT
python 专八/听力/批量/tools/考试视频.py YEAR_DIR stills --sample --out OUT
python 专八/听力/批量/tools/考试视频.py YEAR_DIR stills --out OUT
python 专八/听力/批量/tools/考试视频.py YEAR_DIR audio --audio ORIGINAL_FILE --out OUT
python 专八/听力/批量/tools/考试视频.py YEAR_DIR video --audio ORIGINAL_FILE --out OUT --fast
python 专八/听力/批量/tools/考试视频.py YEAR_DIR video --audio ORIGINAL_FILE --out OUT
```

先运行现成`专八/听力/tools/取字体.py`提取2025原卷同款字体，再开始截图。依赖复用原底座：numpy、soundfile、pyloudnorm、Pillow、playwright、ffmpeg/ffprobe，字体提取另需pypdf/fontTools。Chromium优先实际安装的`chromium`，其次`/opt/pw-browsers/chromium`。

`layout`只检查不写正式截图；正式编码须完整`stills`通过。source_duration和SHA与原始音频相符后，先按原采样率/声道解码浮点WAV，再仅剪授权片头；编码前剪点之外逐样本相同。最终沿用原音匹配（允许AAC误差）、画面切换、CFR、时长、前后静音核验，并额外核编码元信息中的采样率和声道数。

OUT/核验保存画面时间轴核验、排版核验、原音来源核验和最终核查报告。适配器不会调用旧`提交发布.sh`，不会删除或覆盖2025成品，也不会主动推送或发布。批量工作流由总协调单独编排。

## 审核门禁与自检补充

- 根对象的`pending`或`待核`非空时，任何正式制作命令拒绝继续。整理者解决问题并留存证据后置空，不能只为通过门禁清空。
- 草稿可用`schema --draft`作结构预检，或`stills --sample --draft`/`layout --sample --draft`检查带“待核样片·非成品”标记的版式。草稿不得生成正式音轨、视频或全套截图，正式编码不接受草稿排版记录。
- 历史卷先尝试2025原字号/间距，确实不合才按浏览器实际度量，从大到小调整。答题卡37→32px，必要时只移动完整逻辑行平衡两栏，保持左栏再右栏的原文顺序；预览40→30px；单题选项68→48px，题干72→52px；选择题答案43→36px。只有明确标记的长选项/答案允许自然换行，整页越界、边框、块重叠、题间空隙、浅灰线、禁断字检查均保留。最低字号仍放不下即拒绝，制作人须拆`sheets`或`plist.numbers`并根据原音编排换页，不能裁字或继续缩字。
- `sheet_style`和`preview_style`保留作为兼容输入建议并检查下限，最终采用自动最大字号优先的实测结果，见排版报告`fitted_layouts`。4K截图的实际像素为CSS字号两倍。15年现有真实题面合计277个结构压力屏均已通过，答题卡实测33—37px；该检查使用临时时间轴，不等于原音对齐核查。
- 答案泄露检查允许原卷其他位置原本就出现的同词短语，严格按原卷合法出现次数核查，额外出现仍拦截；原题“key issue”等普通用词不会被误作KEY答案标题。单题选项“70.”是选项内容，多题预览和答案页继续完整执行题间距检查。
- `--自检`运行2025数据转换、动态题数/空数、答案分页、不计分标注及7项错误注入；`--自检-排版`运行含不计分标注及原卷合法同词的7个正常屏和6项错误注入（超长选项、额外答案泄露、分隔缺失、未知字形、彩色像素，以及合法同词出现后的额外泄题）。
- 可独立复核成品：`python 考试视频.py YEAR_DIR verify --audio ORIGINAL_FILE --out OUT`。此命令重建原声参考，再对已在OUT的完整MP4运行同一套独立成品检查。
- 排版和最终报告记录`source_fingerprints`：试卷、时间轴、适配器、2025底座四个SHA256。编码前须与完整排版通过记录一致，不能沿用程序或数据更改前的核验。
- 托管浏览器禁用file://时使用本地HTTP挂载。截图HTML按页面指纹命名，禁止HTML缓存，并在DOM中核对渲染指纹，防止旧页面被错误保存成新题截图。
