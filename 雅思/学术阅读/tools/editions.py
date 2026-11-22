"""Production order, released collections and the existing master caches backing them."""
import argparse
import json
import sys
from pathlib import Path

PRODUCTION_BOOKS = {
    '20-11': tuple(range(20, 10, -1)),
    '21': (21,),
    '10-1': tuple(range(10, 0, -1)),
}
COLLECTIONS = {'21-11': ('21', '20-11'), '10-1': ('10-1',)}
PILOT = 'C20T1P1'
PILOT_TAG = 'ielts-academic-20-test-1-passage-1-pilot'


def books(part):
    return [b for group in COLLECTIONS[part] for b in PRODUCTION_BOOKS[group]]


def production_group(book):
    return next(group for group, volumes in PRODUCTION_BOOKS.items() if book in volumes)


def lesson_ids(volumes):
    return [f'C{b}T{t}P{p}' for b in volumes for t in range(1,5) for p in range(1,4)]


def validate_lessons(group, ids):
    if not 1 <= len(ids) <= 20 or len(ids) != len(set(ids)):
        raise ValueError('Select between one and twenty distinct passages')
    extra = set(ids) - set(lesson_ids(PRODUCTION_BOOKS[group]))
    if extra:
        raise ValueError(f'Passages outside production group {group}: {sorted(extra)}')


def missing_masters(group, inventory, project=None):
    assets = inventory('ielts-academic-cache-' + group)
    missing = []
    for pid in lesson_ids(PRODUCTION_BOOKS[group]):
        if pid == PILOT:
            pilot = inventory(PILOT_TAG)
            if not {'Reading-notes.pdf','verification.json','SHA256SUMS'} <= pilot.keys() or not any(n.endswith('.mp4') for n in pilot):
                missing.append(pid)
            continue
        item = assets.get(pid + '-receipt.json')
        if not item and pid == 'C18T1P1':
            # The first generation of running jobs watches the original filename to publish 20–11.
            item = assets.get('collection-21-11.C18T1P1.json')
        if not item or not item['size']:
            missing.append(pid)
            continue
        if group=='21' and project is not None:
            from material import current_key
            try:
                edition=current_key(project,pid)
            except FileNotFoundError:
                missing.append(pid)
                continue
            if f'{pid}-{edition[:16]}.zip' not in assets:
                missing.append(pid)
    return missing


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command',choices=['books','group','ready'])
    parser.add_argument('part')
    args=parser.parse_args()
    if args.command == 'books':
        print(json.dumps(books(args.part)))
    elif args.command == 'group':
        print(production_group(int(args.part)))
    else:
        from release_assets import inventory
        absent = [pid for group in COLLECTIONS[args.part] for pid in missing_masters(group,inventory,Path(__file__).resolve().parents[1])]
        if absent:
            print('Waiting for verified masters: ' + ', '.join(absent),file=sys.stderr)
        print(str(not absent).lower())
