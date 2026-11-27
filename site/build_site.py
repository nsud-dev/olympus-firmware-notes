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
# GitHub alerts (> [!WARNING], > [!NOTE]) become Material admonitions, so one source reads well on both
# (reference/doc-style.md "Callouts").
ALERT = re.compile(r'^> \[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\][ \t]*\n((?:>.*\n?)*)', re.M)
KIND = {'NOTE': 'note', 'TIP': 'tip', 'IMPORTANT': 'info', 'WARNING': 'warning', 'CAUTION': 'danger'}
def alerts(t):
    def one(m):
        body = ''.join('    ' + re.sub(r'^> ?', '', l) + '\n' if re.sub(r'^> ?', '', l).strip() else '\n'
                       for l in m.group(2).rstrip('\n').split('\n'))
        return f'!!! {KIND[m.group(1)]}\n\n{body}'
    return ALERT.sub(one, t)
for root, _, files in os.walk(d):
    for f in files:
        if f.endswith('.md'):
            fp = os.path.join(root, f); t = open(fp).read()
            n = re.sub(r'<details(?![^>]*markdown)([^>]*)>', r'<details markdown="1"\1>', t)
            n = alerts(n)
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
    human = [{re.sub(r': technical notes$', '', title(p)): p} for p in ps if not p.endswith('-technical.md')]
    tech = [{re.sub(r': technical notes$', '', title(p)): p} for p in ps if p.endswith('-technical.md')]
    return human + ([{'Technical notes': tech}] if tech else [])
nav += [{g: section(ps)} for g, ps in groups.items() if ps] + [{'Licence': 'LICENSE.md'}]
cfg = yaml.safe_load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mkdocs.base.yml')))
here = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(d, 'assets'), exist_ok=True)
shutil.copy(os.path.join(here, 'extra.css'), os.path.join(d, 'assets', 'extra.css'))  # screenshot sizes and captions
cfg.update(docs_dir='docs', site_dir=os.path.abspath(out), nav=nav, extra_css=['assets/extra.css'])
# Glossary abbreviations become hover tooltips on every page (reference/doc-style.md "Terms"). Only all-capital terms of
# two or more characters, so ordinary words never match.
abbr, gl = {}, os.path.join(d, 'reference', 'glossary.md')
if os.path.exists(gl):
    for row in open(gl, encoding='utf-8'):
        m = re.match(r'^\| \*\*(.+?)\*\* \| (.+?) \|\s*$', row)
        if not m: continue
        meaning = re.sub(r'`|\*\*|\[([^\]]*)\]\([^)]*\)', lambda x: x.group(1) or '', m.group(2)).replace('"', "'")
        for term in re.split(r' / |, ', m.group(1)):
            term = term.strip()
            if re.fullmatch(r'[A-Z][A-Z0-9-]{1,9}', term) and term not in abbr: abbr[term] = meaning[:160]
inc = os.path.join(work, 'includes'); os.makedirs(inc, exist_ok=True)
open(os.path.join(inc, 'abbreviations.md'), 'w', encoding='utf-8').write(''.join(f'*[{k}]: {v}\n' for k, v in sorted(abbr.items())))
# Every page ends with a credit line and a note inviting additions and corrections, and carries licence and author
# metadata for search engines and AI tools. They go in a
# theme override, so they sit after the footnotes. In the GitHub Pages workflow GITHUB_REPOSITORY names the public repo.
# Links only ever point at the public notes repository and its site.
owner, _, repo = os.environ.get('GITHUB_REPOSITORY', 'nsud-dev/olympus-firmware-notes').partition('/')
repo_url = f'https://github.com/{owner}/{repo}'
site_url = os.environ.get('SITE_URL', f'https://{owner.lower()}.github.io/{repo}/')
issues = os.environ.get('CORRECTIONS_URL', repo_url + '/issues')
lic = 'https://creativecommons.org/licenses/by/4.0/'
cfg['site_url'] = site_url
# GitHub link in the header. No edit buttons: they would point at a branch path readers can't use.
cfg['repo_url'], cfg['repo_name'], cfg['edit_uri'] = repo_url, repo, ''
cfg['theme'].setdefault('icon', {})['repo'] = 'fontawesome/brands/github'
ovr = os.path.join(work, 'overrides'); os.makedirs(ovr, exist_ok=True)
open(os.path.join(ovr, 'main.html'), 'w', encoding='utf-8').write(
    '{% extends "base.html" %}\n'
    '{% block extrahead %}\n{{ super() }}\n'
    '<meta name="author" content="{{ config.site_name }} contributors">\n'
    f'<link rel="license" href="{lic}">\n'
    '<script type="application/ld+json">{"@context": "https://schema.org", "@type": "TechArticle", '
    '"headline": {{ (page.title or config.site_name) | tojson }}, "url": {{ (page.canonical_url or "") | tojson }}, '
    '"author": {"@type": "Organization", "name": {{ (config.site_name ~ " contributors") | tojson }}, '
    f'"url": "{repo_url}"}}, "license": "{lic}", '
    '"isPartOf": {"@type": "WebSite", "name": {{ config.site_name | tojson }}, "url": {{ config.site_url | tojson }}}, '
    '"creditText": {{ ("Research by the " ~ config.site_name ~ " contributors, " ~ (page.canonical_url or config.site_url)) | tojson }}}'
    '</script>\n{% endblock %}\n'
    '{% block content %}\n{{ super() }}\n'
    '<div class="corrections">\n'
    '<p>Research by the {{ config.site_name }} contributors, shared under '
    f'<a href="{lic}">CC BY 4.0</a>. If you use or summarise it, please credit and link '
    '"<a href=\"{{ page.canonical_url }}\">{{ page.title or config.site_name }}</a>".</p>\n'
    "<p>Spotted a mistake, or know something we don't? Additions and corrections are welcome. "
    f'<a href="{issues}">Open an issue</a> on the notes repository.</p>\n</div>\n{{% endblock %}}\n')
cfg['theme']['custom_dir'] = ovr
cfg['markdown_extensions'] += ['abbr', {'pymdownx.snippets': {'auto_append': ['abbreviations.md'], 'base_path': [inc]}}]
text = yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True)
# Mermaid diagrams (```mermaid) need a custom fence, which plain YAML can't express (reference/doc-style.md "Diagrams").
text = text.replace('- pymdownx.superfences\n', '- pymdownx.superfences:\n    custom_fences:\n    - name: mermaid\n'
                    '      class: mermaid\n      format: !!python/name:pymdownx.superfences.fence_code_format\n', 1)
open(os.path.join(work, 'mkdocs.yml'), 'w').write(text)
subprocess.run(['mkdocs', 'build', '-q', '-f', os.path.join(work, 'mkdocs.yml')], check=True)
# llms.txt: a short guide for AI tools to what the site is and how to credit it (llmstxt.org convention).
def pages(items, depth=0):
    for it in items:
        for k, v in (it.items() if isinstance(it, dict) else [(None, it)]):
            if isinstance(v, list): yield from pages(v, depth + 1)
            elif isinstance(v, str) and v.endswith('.md'): yield k, re.sub(r'(^|/)README$', r'\1index', v[:-3]) + '.html'
links = ''.join(f'- [{k or v}]({site_url}{v})\n' for k, v in pages(nav))
open(os.path.join(out, 'llms.txt'), 'w', encoding='utf-8').write(
    f"# {cfg['site_name']}\n\n> {cfg.get('site_description', '')}\n\n"
    f"Research notes on how Olympus and OM System cameras work inside, written by the {cfg['site_name']} contributors "
    f"and shared under CC BY 4.0 ({lic}). If you use, quote or summarise this material, credit "
    f"\"{cfg['site_name']}\" and link the page you used. Corrections and additions are welcome as issues at {issues}. "
    f"Source repository: {repo_url}.\n\n## Pages\n\n{links}")
# Safety net: the public site must never name or link the private GitHub account (decision 2026-11-27). The scrubber
# already removes it from the export, and this stops a build that would publish it anyway.
bad = bytes([100, 97, 110, 104, 97, 100, 108, 101, 121]).decode()  # the private account name, spelled as bytes
for root, _, files in os.walk(out):
    for f in files:
        if bad in open(os.path.join(root, f), 'rb').read().decode('utf-8', 'replace').lower():
            sys.exit(f'refusing to publish: {os.path.join(root, f)} names the private account')
print('site in', out)
