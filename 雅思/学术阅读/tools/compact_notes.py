"""A portable screenshot handout with a full-page baseline JPEG and a 20 MB ceiling."""
import hashlib
import io
import math
import os
from pathlib import Path
import tempfile

import img2pdf
import pymupdf
from PIL import Image, ImageChops, ImageStat

PAGE_POINTS = (960, 540)
MAX_BYTES = 20_000_000
PHONE_WIDTH = 800


def sha(data):
    return hashlib.sha256(data).hexdigest()


def jpeg(image, quality):
    data = io.BytesIO()
    image.save(data, 'JPEG', quality=quality, optimize=True, subsampling=0)
    return data.getvalue()


def phone(image):
    return image.resize((PHONE_WIDTH, PHONE_WIDTH * 9 // 16), Image.Resampling.LANCZOS)


def verify_document(filename, records, size):
    with pymupdf.open(filename) as pdf:
        if len(pdf) != len(records) or filename.stat().st_size > MAX_BYTES:
            raise ValueError('PDF exceeds its page or size specification')
        for page, row in zip(pdf, records):
            images = page.get_images(full=True)
            if len(images) != 1 or page.get_text().strip() or tuple(page.rect)[2:] != PAGE_POINTS:
                raise ValueError(f"Unexpected layout on page {row['page']}")
            xref = images[0][0]
            boxes = page.get_image_rects(xref)
            image = pdf.extract_image(xref)
            if (len(boxes) != 1 or max(abs(a-b) for a,b in zip(boxes[0],page.rect)) > .01
                    or (image['width'], image['height']) != size or image['ext'] != 'jpeg'
                    or sha(image['image']) != row['jpeg_sha256']):
                raise ValueError(f"Embedded screenshot differs on page {row['page']}")


def write_compact(frames, output, title):
    output = Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as tmp:
        tmp = Path(tmp)
        sources, records = [], []
        for im, entry in frames:
            if im.mode != 'RGB' or im.size != (3840,2160):
                raise ValueError('Expected the original full-screen 4K frame')
            raw_sha = sha(im.tobytes())
            if entry.get('rgb_sha256', raw_sha) != raw_sha:
                raise ValueError(f"Wrong source on page {entry['page']}")
            row = {k:entry[k] for k in ('page','screen','frame')}
            row['rgb_sha256'] = raw_sha
            small = im.resize((1600,900),Image.Resampling.LANCZOS)
            im.close()
            path = tmp / f"{row['page']:04}.png"
            small.save(path, compress_level=1)
            sources.append(path)
            records.append(row)
        if not records:
            raise ValueError('Empty handout')
        for width, quality in [(1600,74),(1600,66),(1440,70),(1440,64),(1280,68)]:
            size = (width,width*9//16)
            files = []
            total = 0
            min_psnr = math.inf
            for src,row in zip(sources,records):
                with Image.open(src) as full:
                    im = full if full.size == size else full.resize(size,Image.Resampling.LANCZOS)
                    reference = phone(full)
                    data = jpeg(im,quality)
                    with Image.open(io.BytesIO(data)) as actual:
                        diff = ImageChops.difference(reference,phone(actual))
                        rms = ImageStat.Stat(diff).rms
                        mse = sum(x*x for x in rms)/3
                        psnr = 10*math.log10(255**2/max(mse,1e-8))
                        if psnr < 37:
                            raise ValueError(f"Phone preview differs from the source on page {row['page']}: {psnr:.1f} dB")
                        min_psnr = min(min_psnr,psnr)
                jpg = src.with_suffix('.jpg')
                jpg.write_bytes(data)
                files.append(str(jpg))
                row['jpeg_sha256'] = sha(data)
                total += len(data)
            if total > MAX_BYTES:
                continue
            candidate = tmp/'handout.pdf'
            with candidate.open('wb') as f:
                img2pdf.convert(*files,outputstream=f,engine=img2pdf.Engine.internal,
                                layout_fun=img2pdf.get_layout_fun(pagesize=PAGE_POINTS,fit=img2pdf.FitMode.exact),
                                title=title,nodate=True)
            if candidate.stat().st_size > MAX_BYTES:
                continue
            verify_document(candidate,records,size)
            os.replace(candidate,output)
            return dict(source='final_mp4',pages=len(records),layout='16:9, full bleed',
                        pixel_dimensions=list(size),source_pixel_dimensions=[3840,2160],
                        compression='JPEG 4:4:4',jpeg_quality=quality,bytes=output.stat().st_size,
                        byte_limit=MAX_BYTES,phone_width=PHONE_WIDTH,min_phone_psnr_db=round(min_psnr,2),
                        frames=records)
        raise ValueError('Unable to fit all legible screenshots within 20 MB')
