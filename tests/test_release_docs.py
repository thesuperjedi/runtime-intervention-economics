"""Release-candidate documentation checks; no external services or identity inference."""
import unittest,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class ReleaseDocumentationTests(unittest.TestCase):
    def test_confirmed_mononym_has_no_invented_identity(self):
        c=json.loads((ROOT/'CITATION.cff').read_text(encoding='utf-8'))
        self.assertEqual(c['cff-version'],'1.2.0')
        self.assertEqual(c['authors'],[{'given-names':'Jaidev'}])
        self.assertNotIn('DRAFT',c['message'])
        self.assertNotIn('family-names',c['authors'][0])
        self.assertNotIn('affiliation',c['authors'][0])
        self.assertIn('Independent Researcher',c['abstract'])
        for key in ('doi','date-released','repository-code','url','license','preferred-citation','contact'):
            self.assertNotIn(key,c)
    def test_confirmed_attribution_not_institution(self):
        t=(ROOT/'ATTRIBUTION.md').read_text(encoding='utf-8')
        self.assertIn('not an institutional affiliation',t)
        for field in ('Jaidev','GitHub username','email address','ORCID'):
            self.assertIn(field,t)
    def test_approved_licences_are_scoped(self):
        self.assertTrue((ROOT/'LICENSE.md').is_file())
        self.assertIn('Copyright (c) 2026 Jaidev',(ROOT/'LICENSES/MIT.txt').read_text(encoding='utf-8'))
        self.assertIn('Section 8 -- Interpretation.',(ROOT/'LICENSES/CC-BY-4.0.txt').read_text(encoding='utf-8'))
        t=(ROOT/'LICENSE_SCOPE.md').read_text(encoding='utf-8')
        self.assertIn('no blanket author licence',t)
        self.assertIn('response_text',t)
        self.assertIn('CC BY4.0',t)
    def test_readme_local_links_resolve(self):
        text=(ROOT/'README.md').read_text(encoding='utf-8')
        for href in re.findall(r'\]\(([^)]+)\)',text):
            if '://' not in href:self.assertTrue((ROOT/href.split('#')[0]).is_file(),href)
    def test_three_reproduction_modes_explicit(self):
        t=(ROOT/'README.md').read_text(encoding='utf-8')
        for label in ('Scientific-calculation reproduction','Historical raw-record authenticity','Fresh model execution'):
            self.assertIn(label,t)
    def test_worked_example_boundaries(self):
        text=(ROOT/'docs/adapting-a-domain.md').read_text(encoding='utf-8')
        code=re.search(r'```python\n(.*?)```',text,re.S).group(1)
        ns={};exec(compile(code,'documented-example','exec'),ns)
        oracle=ns['expense_controls']
        for amount in (999,1000,1001):
            for confidential in (False,True):
                for external in (False,True):
                    expected=set()
                    if amount>1000:expected.add('MANAGER_APPROVAL')
                    if confidential and external:expected.add('SECURITY_REVIEW')
                    self.assertEqual(oracle(amount,confidential,external),expected)
        with self.assertRaises(ValueError):oracle(-1,False,False)
