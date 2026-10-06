# 四级词汇范围（用于判断词条是“四级词”还是“超纲词”）

- `初中.txt`（1987 词）、`高中.txt`（3743 词）、`四级.txt`（4992 词）
- 来源：开源词库 KyleBing/english-vocabulary（经 npm 包 @ssbun/ev-cli 0.1.0 的 data/junior、senior、cet4）
  与 cet-words-cli 0.3.1 的四级词条合并去重。
- 规则：词头（原形）在三份词表的并集里 → 四级词（标注时不加前缀）；不在 → 超纲词（标注时加 *）。
  派生词不在表里也算超纲（如 unattainable）。个别人工裁定写在 `../词级已核.json`。
