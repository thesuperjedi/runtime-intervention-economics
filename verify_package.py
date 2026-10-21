"""Read-only release integrity check; no workspace outside this package is needed."""
import json,hashlib
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from scan_release import scan,package_files
ROOT=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def verify():
 inventory=json.loads((ROOT/'provenance/package_inventory.json').read_text())['files_sha256']
 current={p.relative_to(ROOT).as_posix():sha(p) for p in package_files(ROOT) if p.relative_to(ROOT).as_posix()!='provenance/package_inventory.json'}
 if current!=inventory:raise ValueError('Package inventory mismatch: missing/extra/modified files')
 mapping=json.loads((ROOT/'provenance/projection_map.json').read_text())
 for r in mapping['observation_records']:
  if sha(ROOT/r['public'])!=r['public_sha256']:raise ValueError('Projection changed')
 result=scan()
 if result['findings']:raise ValueError('Release scan requires review')
 return dict(status='PASS',files_verified=len(current),observation_projections=2880,scan=result,
             note='Original SHA references are traceability evidence, not independently authenticatable raw evidence.')
if __name__=='__main__':print(json.dumps(verify(),indent=2))
