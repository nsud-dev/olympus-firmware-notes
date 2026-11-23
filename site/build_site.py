#!/usr/bin/env python3
"""Build the notes site (MkDocs Material) from a folder that holds docs/.
  pip install -r site/requirements.txt
  python3 -I site/build_site.py . _site      # in the notes repo: the folder with docs/, then the output folder
Nav order: guides in guides/README.md order, then Features / Hardware / Firmware / Bodies / Reference / Tools in docs/README.md
order, then any page the README doesn't list. The GitHub Pages workflow (.github/workflows/pages.yml) runs this."""
import os, re, shutil, subprocess, sys, tempfile, yaml
exp, out = sys.argv[1:3]
work = tempfile.mkdtemp(prefix='olysite-'); d = os.path.join(work, 'docs')
shutil.copytree(os.path.join(exp, 'docs'), d)
# Tables and lists inside <details> render only with md_in_html's markdown="1" (GitHub renders them without it).
for root, _, files in os.walk(d):
    for f in files:
        if f.endswith('.md'):
            fp = os.path.join(root, f); t = open(fp).read()
            n = re.sub(r'<details(?![^>]*markdown)([^>]*)>', r'<details markdown="1"\1>', t)
            if n != t: open(fp, 'w').write(n)
def links(p, pre=''): return [pre + m for m in re.findall(r'\]\(([\w/.-]+\.md)\)', open(os.path.join(d, p)).read())]
def title(p):
    for l in open(os.path.join(d, p)):
        if l.startswith('# '): return l[2:].strip()
    return p
seen = set()
def take(p):
    if p in seen or not os.path.exists(os.path.join(d, p)): return False
    seen.add(p); return True
guides = [p for p in ['guides/README.md'] + links('guides/README.md', 'guides/') if take(p)]
groups = {g: [] for g in ['Features', 'Hardware', 'Firmware', 'Bodies', 'Reference', 'Tools']}
folder = {'features': 'Features', 'patches': 'Features', 'hardware': 'Hardware', 'firmware': 'Firmware',
          'bodies': 'Bodies', 'reference': 'Reference', 'tools': 'Tools'}
for p in links('README.md'):
    if p.split('/')[0] in folder and take(p): groups[folder[p.split('/')[0]]].append(p)
for f, g in folder.items():
    for n in sorted(os.listdir(os.path.join(d, f))) if os.path.isdir(os.path.join(d, f)) else []:
        if take(f'{f}/{n}'): groups[g].append(f'{f}/{n}')
nav = [{'Home': 'README.md'}, {'Overview': 'overview.md'}, {'Guides': [{title(p): p} for p in guides]}]
# Human pages first. Each section's technical sister pages go in one collapsed "Technical notes" group.
def section(ps):
    human = [{title(p): p} for p in ps if not p.endswith('-technical.md')]
    tech = [{re.sub(r': technical notes$', '', title(p)): p} for p in ps if p.endswith('-technical.md')]
    return human + ([{'Technical notes': tech}] if tech else [])
nav += [{g: section(ps)} for g, ps in groups.items() if ps] + [{'Licence': 'LICENSE.md'}]
cfg = yaml.safe_load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mkdocs.base.yml')))
here = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(d, 'assets'), exist_ok=True)
shutil.copy(os.path.join(here, 'extra.css'), os.path.join(d, 'assets', 'extra.css'))  # screenshot sizes and captions
cfg.update(docs_dir='docs', site_dir=os.path.abspath(out), nav=nav, extra_css=['assets/extra.css'])
yaml.safe_dump(cfg, open(os.path.join(work, 'mkdocs.yml'), 'w'), sort_keys=False, allow_unicode=True)
subprocess.run(['mkdocs', 'build', '-q', '-f', os.path.join(work, 'mkdocs.yml')], check=True)
print('site in', out)
