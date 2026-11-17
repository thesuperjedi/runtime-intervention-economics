"""Run only the publication tests, with socket connections prohibited."""
from pathlib import Path
import sys
import socket
import unittest

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

def denied(*args, **kwargs):
    raise RuntimeError("Network disabled for publication verification")

def main():
    if sys.argv[1:] not in ([], ["--mechanism"]):
        raise SystemExit("Supported: no arguments for 36 publication tests, or --mechanism")
    mechanism = sys.argv[1:] == ["--mechanism"]
    if mechanism:
        from mechanism.offline_guard import install
        install(ROOT)
    socket.socket.connect = denied
    socket.create_connection = denied
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_mechanism.py" if mechanism else "test_release.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print("PUBLICATION_TEST_COUNTS", result.testsRun, "failures", len(result.failures), "errors", len(result.errors))
    return 0 if result.wasSuccessful() else 1

if __name__ == "__main__":
    sys.exit(main())
