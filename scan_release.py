"""Bounded local content scan: reports locations/categories only, never secret values."""
import re,json,ast,os
from pathlib import Path
ROOT=Path(__file__).resolve().parent
PATTERNS={
 'google_api_key':r'AIza[0-9A-Za-z_-]{35}',
 'private_key':r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
 'bearer_token':r'Bearer\s+[A-Za-z0-9_.-]{20,}',
 'personal_absolute_path':r'(?i)(?:[A-Z]:[/\\]+Users[/\\]+[^/\\\s"]+|[/]Users[/][^/\s"]+|[/]home[/][^/\s"]+)',
 'email':r'\b[A-Za-z0-9_.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'}
FORBIDDEN_FIELDS={'provider_interaction_id','interaction_id','raw_provider_response','sdk_serialized_response','signature','email','hostname','username','project_id','billing_account','api_key','access_token','refresh_token'}
def traversal_error(error):
 raise error
def traversal_error(error):
 raise error
def package_files(root):
 # Only the root Git administrative directory is outside the release payload.
 # Do not consult .gitignore: ignored/untracked payload files still require checks.
 for base,dirs,names in os.walk(root,followlinks=False,onerror=traversal_error):
  base=Path(base)
  for name in list(dirs):
   item=base/name
   if item.is_symlink() or item.is_junction():
    raise ValueError('Linked directory is not a release file')
   if base==root and name=='.git':
    dirs.remove(name)
  for name in names:
   item=base/name
   if item.is_symlink():
    raise ValueError('Linked file is not a release file')
   yield item
def scan():
 findings=[]
 files=list(package_files(ROOT))
 for p in files:
  relative=p.relative_to(ROOT).as_posix()
  if any(x in p.parts for x in ('.git','.venv','.idea','__pycache__')) or p.name=='.env' or p.suffix in ('.zip','.pyc','.pem','.key'):
   findings.append(dict(file=relative,category='unexpected_artifact'))
  if p.suffix not in ('.py','.json','.md','.txt','.patch','.cff') and p.name not in ('.gitignore',):
   findings.append(dict(file=relative,category='unexpected_extension'))
  text=p.read_text(encoding='utf-8')
  for category,pattern in PATTERNS.items():
   if re.search(pattern,text):findings.append(dict(file=relative,category=category))
  if relative.startswith('data/raw/') and p.suffix=='.json':
   rec=json.loads(text)
   if set(rec)&FORBIDDEN_FIELDS:findings.append(dict(file=relative,category='forbidden_observation_metadata'))
 return dict(status='PASS_BOUNDED_SCAN' if not findings else 'REVIEW_REQUIRED',files_scanned=len(files),
             findings=findings,scope='Text regex, observation-field and file-type allowlist checks; not security clearance or legal approval.')
if __name__=='__main__':print(json.dumps(scan(),indent=2))
