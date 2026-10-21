"""stdlib-only scientific suite; isolated from SDK, network and private workspace."""
import sys,unittest,importlib.util,inspect,socket,os
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT),str(ROOT/'e3_phase1')]
def denied(*a,**k):raise RuntimeError('network disabled')
socket.socket.connect=denied;socket.create_connection=denied
def main():
    suite=unittest.TestSuite()
    files=sorted((ROOT/'tests').glob('test_*.py'))+sorted((ROOT/'e3_phase1').glob('test_*.py'))+sorted((ROOT/'extensions/overlap_v1/analysis').glob('test_*.py'))
    for i,p in enumerate(files):
        spec=importlib.util.spec_from_file_location('public_test_'+str(i),p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(m))
        # Original E1 policy functions use bare assertions, with no pytest fixtures.
        for name,f in inspect.getmembers(m,inspect.isfunction):
            if name.startswith('test_') and not inspect.signature(f).parameters:suite.addTest(unittest.FunctionTestCase(f,description=p.name+':'+name))
    result=unittest.TextTestRunner(verbosity=1).run(suite)
    print('PUBLIC_TEST_COUNTS',result.testsRun,'failures',len(result.failures),'errors',len(result.errors))
    return not result.wasSuccessful()
if __name__=='__main__':sys.exit(main())
