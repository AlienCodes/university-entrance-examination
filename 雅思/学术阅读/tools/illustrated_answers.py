"""Bind an answer booklet to its reading passage, evidence and on-screen artwork."""
import base64
from io import BytesIO
import re
import unicodedata

from illustration_stage import ART, illustration, read


def applies(pid):
    return re.fullmatch(r'C(?:[6-9]|1[0-3])T[1-4]P[1-3]', pid) is not None


def words(text):
    return ' '.join(re.findall(r'[a-z0-9]+', unicodedata.normalize('NFKC', text).casefold()))


def check_reasoning(lesson, question, note):
    name = f"{lesson['lesson']} Q{question['numbers'][0]}"
    fields = [note.get(key, '').strip() for key in ('focus', 'locate', 'logic', 'check')]
    if len(set(fields)) != 4 or any(not re.search(r'[\u3400-\u9fff]', field) for field in fields):
        raise ValueError(f'{name}: missing or repeated steps in the explanation')
    if note.get('answer') != question['answer']:
        raise ValueError(f'{name}: conclusion differs from the paper key')
    indexes = note['evidence']
    if (not indexes or len(set(indexes)) != len(indexes) or not set(question['evidence']) <= set(indexes)
            or any(type(i) is not int or not 1 <= i <= len(lesson['sentences']) for i in indexes)):
        raise ValueError(f'{name}: invalid evidence sentence numbers')
    fragment = words(note['quote'])
    if len(fragment.split()) < 2 or not any(
        ' ' + fragment + ' ' in ' ' + words(lesson['sentences'][i-1]['en']) + ' ' for i in indexes
    ):
        raise ValueError(f'{name}: key quotation does not occur in the cited passage')
    choices = question.get('options') or question.get('word_bank', {})
    selected = set(re.split(r'\s*[、,]\s*', question['answer']))
    rejected = note['distractors']
    labels = [r['option'] for r in rejected]
    if (len(set(labels)) != len(labels) or any(k not in choices or k in selected for k in labels)
            or any(not re.search(r'[\u3400-\u9fff]', r['why']) for r in rejected)):
        raise ValueError(f'{name}: invalid rejected option')
    if question['kind'] in ('One Choice', 'Two Choices') and (
        not selected <= set(choices) or set(labels) != set(choices) - selected
    ):
        raise ValueError(f'{name}: an actual choice still lacks an explanation')


def receipt_matches(pid, receipt, art_sha):
    if (receipt.get('lesson') != pid or receipt.get('full_movie') is not True
            or receipt.get('illustration_sha256') != art_sha
            or (receipt.get('plate_start'), receipt.get('plate_frames'), receipt.get('first_reading_frame')) != (45, 30, 75)
            or not re.fullmatch(r'[a-f0-9]{64}', receipt.get('video_sha256', ''))):
        raise ValueError(pid + ': the film and the answer booklet do not share the approved illustration')


def artwork(lesson, movie):
    pid = lesson['lesson']
    art_sha = illustration(pid)
    receipt_matches(pid, movie, art_sha)
    design = read(ART / '篇目.json')[pid]
    paper = read(ART.parent / '原稿' / (pid + '.json'))
    title = paper.get('title_zh') or read(ART.parent / '篇目' / pid / '篇目信息.json')['title_zh']
    if lesson['display_title'] != f"{design['book']}-{design['test']}-{design['passage']} {title}":
        raise ValueError(pid + ': booklet title does not match the film and printed passage')
    return ART / '插画' / (pid + '.webp'), art_sha


def image_tag(path):
    from PIL import Image

    # Chromium embeds JPEG directly. Decoded WebP is otherwise written as a multi-MB bitmap.
    encoded = BytesIO()
    with Image.open(path) as picture:
        picture.convert('RGB').save(encoded, format='JPEG', quality=91, subsampling=0, optimize=True)
    payload = base64.b64encode(encoded.getvalue()).decode('ascii')
    return f'<img class="passage-art" width="1600" height="900" alt="本篇视频的篇首插图" src="data:image/jpeg;base64,{payload}">'


def check_first_page(pdf_path, lesson, movie):
    import fitz
    from PIL import Image, ImageChops, ImageStat

    source, art_sha = artwork(lesson, movie)
    with fitz.open(pdf_path) as pdf, Image.open(source) as original:
        page = pdf[0]
        images = page.get_image_info(xrefs=True)
        if len(images) != 1:
            raise ValueError(f'{pdf_path}: expected one visible illustration on the opening page')
        item = images[0]
        box = fitz.Rect(item['bbox'])
        if ((item['width'], item['height']) != original.size or abs(box.width / box.height - 16/9) > .01
                or not page.rect.contains(box) or box.width < page.rect.width * .7):
            raise ValueError(f'{pdf_path}: illustration is cropped, missing or too small')
        title = lesson['display_title'].split(' ', 1)[1]
        normalize = lambda s: ''.join(unicodedata.normalize('NFKC', s).split())
        above = page.get_text(clip=fitz.Rect(0, 0, page.rect.width, box.y0))
        if normalize(title) not in normalize(above):
            raise ValueError(f'{pdf_path}: article title must appear above the illustration')
        # Compare the visible printed page, including any clipping, masks or overlays.
        pix = page.get_pixmap(clip=box, colorspace=fitz.csRGB, alpha=False)
        visible = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
        target = (256, 144)
        difference = ImageChops.difference(visible.resize(target, Image.Resampling.LANCZOS),
                                           original.convert('RGB').resize(target, Image.Resampling.LANCZOS))
        error = sum(ImageStat.Stat(difference).mean) / 3
        if error > 4:
            raise ValueError(f'{pdf_path}: printed picture differs from film illustration (mean error {error:.2f})')
        return dict(lesson=lesson['lesson'], page=1, illustration_sha256=art_sha,
                    video_sha256=movie['video_sha256'], image_error_255=round(error, 3))
