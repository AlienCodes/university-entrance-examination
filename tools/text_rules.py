"""各项目共用的文字规则（只写在这一处，踩坑 30、41、60a、73）。

word_count：片头“全文 N 词”。按空白、破折号（— –）、省略号切分，只数含英文字母或数字的片段：
  中文注释“(防水布)”不算词（踩坑 30，中考）；villages—just 算两个词（踩坑 41，中考 / 考研）。
  专八、四级、六级的提取程序当年用的是 len(text.split())，中文注释算成一个词、破折号连着的两个词算一个
  （专八 t09 片头 1079 词，应为 1094；防复发审计 2026-10-23 查出）。build_vocab 一律从定稿句子用这里重算，不用提取时存的数。"""
import re


def word_count(text):
    return len([w for w in re.split(r'[\s—–…]+', text) if re.search(r'[A-Za-z0-9]', w)])
