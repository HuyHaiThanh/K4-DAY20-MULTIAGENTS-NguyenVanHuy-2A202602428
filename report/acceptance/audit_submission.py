"""Final local consistency gates; does not call a model or expose credentials."""
import ast
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from dotenv import dotenv_values
from lab.compare import build_table, load_runs
from lab.curator import validate_skill
from lab.tasks import hash_skills

root = Path.cwd()
runs = load_runs()
assert len(runs) == 18, "Expected 18 final runs"
status = json.loads(Path('report/official-status.json').read_text())
assert status['official_experiments_complete'] and status['valid_final_records_present'] == len(runs)
assert status['final_runs_tokens'] == sum(r['tokens']['total'] for r in runs)
assert len({(r['condition'], r['task']) for r in runs}) == 18
for r in runs:
    assert not r['error'], (r['condition'], r['task'], r['error'])
    assert r['tokens']['total'] > 0 and r['total'] == len(r['checks'])
    assert r['passed'] == sum(bool(c['passed']) for c in r['checks'])
    assert abs(r['score'] - r['passed']/r['total']) < 1e-12
    assert not r['skills_modified']
    cfg = json.loads((Path('results')/r['condition']/r['task']/'configuration.json').read_text())
    assert cfg == json.loads(Path('report/acceptance/openai-configuration.json').read_text())
assert Path('report/table.md').read_text().strip() == build_table(runs).strip()
assert len(list(Path('results/skills-auto-dev').glob('*/run.json'))) == 3
for p in Path('results/skills-auto-dev').glob('*/run.json'):
    r = json.loads(p.read_text())
    assert not r['error'] and not r['skills_modified']
    assert r['skills_sha256'] == hash_skills(Path('skills/auto'))
    assert json.loads(p.with_name('configuration.json').read_text()) == json.loads(Path('report/acceptance/openai-configuration.json').read_text())
skills = list(Path('skills/auto').glob('*/SKILL.md'))
assert len(skills) == 3
for p in skills:
    assert not validate_skill(p.read_text(), p.parent.name)
for r in runs:
    if r['condition'] == 'skills-auto':
        assert r['skills_sha256'] == hash_skills(Path('skills/auto'))
verify = subprocess.run([sys.executable, 'scripts/verify_freeze.py'], capture_output=True, text=True)
assert verify.returncode == 0, verify.stdout + verify.stderr
protected = subprocess.check_output(['git','ls-tree','-r','--name-only','d982034'], text=True).splitlines()
protected = [p for p in protected if p.startswith(('tasks/','tests/','scripts/')) or
    p in ('src/lab/model.py','src/lab/tasks.py','src/lab/grading.py','src/lab/testing.py','src/lab/compare.py')]
assert not subprocess.check_output(['git','diff','d982034','--',*protected], text=True, stderr=subprocess.PIPE).strip()
for rel, names in {
    'src/lab/agent.py': ['PATHS_NOTE','BASE_PROMPT','SKILLS_NOTE','SUBAGENTS_NOTE'],
    'src/lab/runner.py': ['CONDITIONS','render_trace','main'],
    'src/lab/curator.py': ['SAFE_NAME','validate_skill','parse_skill_blocks'],
}.items():
    def selected(text):
        out = {}
        for node in ast.parse(text).body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = node.name
            elif isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
                name = node.targets[0].id
            else:
                continue
            if name in names: out[name] = ast.dump(node, include_attributes=False)
        return out
    original = subprocess.check_output(['git','show','d982034:'+rel], text=True, encoding='utf-8')
    assert selected(original) == selected(Path(rel).read_text(encoding='utf-8')), rel
key = dotenv_values('.env').get('AZURE_OPENAI_KEY')
assert key and subprocess.run(['git','check-ignore','.env'], capture_output=True).returncode == 0
credential_hits = []
old_provider_hits = []
for base in ('report','results','skills','src','scripts'):
    for p in Path(base).rglob('*'):
        if p.is_file() and p.suffix in ('.md','.py','.json','.jsonl','.txt','.log','.xml'):
            content = p.read_bytes()
            if key.encode() in content: credential_hits.append(str(p))
            if base == 'report' and p.suffix == '.md' and any(s in content.lower() for s in (b'qwen',b'gpt-oss',b'groq',b'gemini')):
                old_provider_hits.append(str(p))
assert not credential_hits, 'Credential found; do not publish'
assert not old_provider_hits, old_provider_hits
xml = ET.parse('report/acceptance/pytest-final-review.xml')
suites = list(xml.getroot().iter('testsuite'))
passed = sum(int(s.attrib['tests']) - int(s.attrib.get('failures',0)) - int(s.attrib.get('errors',0)) - int(s.attrib.get('skipped',0)) for s in suites)
assert passed == 85 and all(int(s.attrib.get('failures',0)) == int(s.attrib.get('errors',0)) == 0 for s in suites)
diff = subprocess.run(['git','diff','--check'], capture_output=True, text=True)
assert diff.returncode == 0, diff.stdout
cached = subprocess.run(['git','diff','--cached','--check'], capture_output=True, text=True)
assert cached.returncode == 0, cached.stdout
Path('report/acceptance/git-diff-check.json').write_text(json.dumps({'command':'git diff --check','exit_code':diff.returncode,'stdout':diff.stdout,'line_ending_warnings':bool(diff.stderr)},indent=2)+'\n')
out = {'final_runs':len(runs),'development_runs':3,'valid_skills':len(skills),'tests_passed':passed,
    'table_matches_records':True,'git_diff_check':True,'git_cached_diff_check':True,'all_configs_identical':True,'provided_unchanged':True,
    'provided_ast_unchanged':True,'credentials_found':False,'old_provider_report_mentions':False,
    'freeze_check':verify.stdout.strip(),'frozen_skills_hash':hash_skills(Path('skills/auto'))}
Path('report/acceptance/submission-audit.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out), flush=True)
