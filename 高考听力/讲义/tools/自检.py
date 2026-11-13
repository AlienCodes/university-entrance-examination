"""对交付关卡做正常与故障验证；测试只写临时文件，不修改成品或题目。"""
import copy
import json
import tempfile
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, NameObject
import 制作 as M


def rejects(action, label):
    try:
        action()
    except AssertionError:
        print('已拦住：' + label)
        return
    raise AssertionError('故障未被拦住：' + label)


def main():
    cases = M.data(False)
    manifest = json.loads((M.OUT / '文件清单与核验.json').read_text())
    assert M.verify_model(cases) == manifest['dictation_blanks']
    bad = copy.deepcopy(cases[0])
    q = bad['questions'][0]
    q['answer'] = next(k for k in q['options'] if k != q['answer'])
    rejects(lambda: M.verify_model([bad]), '参考答案偏离已发布数据')

    path = M.OUT / '07 高考英语听力真题参考答案.pdf'
    original = PdfReader(path)
    es, _ = M.compose('answers', cases)
    numbers = {mark: original.get_destination_page_number(o) + 1 for (mark, *_), o in zip(es, original.outline)}
    M.check_pdf(path, es, numbers, 'answers', cases)
    with tempfile.TemporaryDirectory(prefix='gaokao-handout-negative-') as tmp:
        writer = PdfWriter(clone_from=path)
        changed = False
        for page in writer.pages:
            for ref in page.get('/Annots') or []:
                obj = ref.get_object()
                if obj.get('/Subtype') == '/Link' and isinstance(obj.get('/Dest'), ArrayObject):
                    obj[NameObject('/Dest')] = ArrayObject([writer.pages[-1].indirect_reference, NameObject('/Fit')])
                    changed = True
                    break
            if changed:
                break
        assert changed
        target = Path(tmp) / 'wrong-toc.pdf'
        writer.write(target)
        rejects(lambda: M.check_pdf(target, es, numbers, 'answers', cases), '目录链接指向错误章节')
    print('正常成品通过，两个实质故障均被拦住；源材料及成品未修改。')


if __name__ == '__main__':
    main()
