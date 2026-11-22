"""Editable editor-facing preliminary response; OPEN points clearly marked."""
from pathlib import Path
from docx import Document
from docx.shared import Inches,Pt,RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
root=Path(__file__).resolve().parents[1]
lines=(root/'REVIEWER_RESPONSE.md').read_text(encoding='utf-8').splitlines()
d=Document();s=d.sections[0];s.top_margin=Inches(.72);s.bottom_margin=Inches(.72)
s.left_margin=Inches(.85);s.right_margin=Inches(.85)
normal=d.styles['Normal'];normal.font.name='Times New Roman';normal.font.size=Pt(10)
normal.paragraph_format.space_after=Pt(7)
for i,line in enumerate(lines):
    if not line.strip():continue
    line=line.strip().replace('**','').replace('*','').replace('`','')
    if line.startswith('# '):d.add_heading(line[2:],0)
    elif line.startswith('## '):d.add_heading(line[3:],1)
    elif line.startswith('**Reviewer') or line.startswith('Reviewer'):
        if '—' in line:
            first,tail=line.split('—',1)
            p=d.add_paragraph();r=p.add_run(first+'—');r.bold=True;p.add_run(tail)
        else:d.add_paragraph(line)
    else:d.add_paragraph(line)
d.core_properties.title='Preliminary Response to Reviewer — Hydrogen Hierarchical RL Paper'
out=root/'manuscript'/'Reviewer_Response_to_Comments.docx';d.save(out)
print(out)
