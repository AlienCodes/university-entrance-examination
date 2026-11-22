"""Export both Bilibili sizes from their independent, fully typeset artwork."""
import subprocess
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile, ZipInfo

HERE = Path(__file__).resolve().parent
EDITIONS = {'21-11': 'C17T1P1-21-11', '10-1': 'C10T1P1'}
WIDTHS = {'16x9': 1920, '4x3': 1440}
HEIGHT = 1080


def size(path):
    dimensions = subprocess.check_output(
        ['magick', 'identify', '-format', '%w %h', str(path)], text=True
    )
    return tuple(map(int, dimensions.split()))


def export(edition, passage, ratio, width):
    source = HERE / '原图' / f'{passage}-{ratio}.png'
    original_width, original_height = size(source)
    if abs(original_width - original_height * width / HEIGHT) > 2:
        raise ValueError(f'Wrong source aspect ratio: {source.name}')
    dest = HERE / f'Cambridge-IELTS-{edition}-{ratio}.jpg'
    subprocess.run([
        'magick', str(source), '-colorspace', 'sRGB',
        '-resize', f'{width}x{HEIGHT}!', '-strip',
        '-sampling-factor', '4:4:4', '-quality', '91', str(dest)
    ], check=True)
    if size(dest) != (width, HEIGHT) or dest.stat().st_size > 2_000_000:
        raise ValueError(f'Unexpected image size: {dest.name}')
    return dest


if __name__ == '__main__':
    assets = [
        export(edition, passage, ratio, width)
        for edition, passage in EDITIONS.items()
        for ratio, width in WIDTHS.items()
    ]
    pack = HERE / 'Cambridge-IELTS-Bilibili-Covers.zip'
    with ZipFile(pack, 'w', compression=ZIP_STORED) as archive:
        for asset in assets:
            archive.writestr(ZipInfo(asset.name), asset.read_bytes())
    with ZipFile(pack) as archive:
        if archive.testzip() or archive.namelist() != [asset.name for asset in assets]:
            raise ValueError('Incomplete cover archive')
        for asset in assets:
            if archive.read(asset.name) != asset.read_bytes():
                raise ValueError(asset.name)
