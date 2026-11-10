#!/usr/bin/env python3
"""Prepare a non-destructive import from the downloaded 16-paper ZIP.

Run from the repository root:
    python publication_archive/scripts/import_publications.py /path/to/PhD_Publications_Rewritten_Manuscripts_2026-11-10.zip

This creates the full file layout under publication_archive/ but does not git add,
commit, or push. Review rights to publish source drafts before committing.
"""
from pathlib import Path
from zipfile import ZipFile
import sys

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / 'publication_archive'
MAPPING = {
    'Manuscript_Revised.docx': 'manuscript/Manuscript_Revised.docx',
    'Manuscript_Revised.pdf': 'manuscript/Manuscript_Revised.pdf',
    'Manuscript_Revised.md': 'manuscript/Manuscript_Revised.md',
    'references_to_verify.bib': 'references/references_to_verify.bib',
    'EDITORIAL_NOTES.md': 'audit/EDITORIAL_NOTES.md',
    'REFERENCE_AUDIT.md': 'audit/REFERENCE_AUDIT.md',
    'REPRODUCIBILITY_CHECKLIST.md': 'audit/REPRODUCIBILITY_CHECKLIST.md',
}

def main(zip_path):
    if not zip_path.is_file():
        raise SystemExit(f'Archive not found: {zip_path}')
    count = 0
    with ZipFile(zip_path) as z:
        if z.testzip():
            raise SystemExit('Corrupted ZIP archive')
        for info in z.infolist():
            if info.is_dir():
                continue
            parts = Path(info.filename).parts
            first = next((i for i, part in enumerate(parts) if part.startswith('P') and len(part) > 3 and part[1:3].isdigit()), None)
            if first is None:
                continue
            paper, *sub = parts[first:]
            if not sub:
                continue
            rel = Path(*sub)
            if rel.name in MAPPING and len(sub) == 1:
                target = DEST / paper / MAPPING[rel.name]
            elif rel.parts[0] == 'Source_Figures':
                target = DEST / paper / 'figures' / Path(*rel.parts[1:])
            elif rel.name.startswith('Source_') or rel.name == 'SOURCE_AVAILABILITY.txt':
                target = DEST / paper / 'sources' / rel
            else:
                target = DEST / paper / 'source_misc' / rel
            if target.exists():
                raise SystemExit(f'Refusing to overwrite {target}')
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as source, target.open('wb') as output:
                while chunk := source.read(1024 * 1024):
                    output.write(chunk)
            count += 1
    print(f'Imported {count} files to {DEST}')
    print('Review source redistribution permissions, then commit and push using git.')

if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: import_publications.py <16-paper-archive.zip>')
    main(Path(sys.argv[1]))
