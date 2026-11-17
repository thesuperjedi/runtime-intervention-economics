"""Diagnostic guards for cooperative TEST-ONLY demos, not hostile-process isolation."""
from pathlib import Path
import os
import socket
import sys
_INSTALLED = False

class CredentialBlindEnvironment(dict):
    def _deny(self, *args, **kwargs):
        raise RuntimeError("Credential/environment reads are prohibited")
    __getitem__ = get = copy = keys = values = items = __iter__ = _deny

def install(root):
    global _INSTALLED
    if _INSTALLED:
        return
    roots = (Path(root).resolve(), Path(sys.base_prefix).resolve())
    allowed = set(sys.stdlib_module_names) | {"mechanism", "verify_package", "test_mechanism"}
    def deny(*args, **kwargs):
        raise RuntimeError("Network access prohibited in TEST-ONLY demo")
    def audit(event, args):
        if event == "import" and args and str(args[0]).split(".")[0] not in allowed:
            raise RuntimeError("Non-stdlib/non-demo import prohibited")
        if event.startswith("socket.") or event in {"subprocess.Popen", "os.system", "os.exec", "os.posix_spawn"}:
            raise RuntimeError("Network/process execution prohibited")
        if event == "open" and args and not isinstance(args[0], int):
            p = Path(args[0]).resolve()
            mode = args[1] if len(args) > 1 else None
            flags = args[2] if len(args) > 2 and isinstance(args[2], int) else 0
            if any(x in (mode or "") for x in ("w", "a", "x", "+")) or flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
                raise RuntimeError("Demo filesystem writes prohibited")
            if not any(p.is_relative_to(r) for r in roots):
                raise RuntimeError("Read outside demo/stdlib scope prohibited")
        if event in {"os.mkdir", "os.remove", "os.rename", "os.rmdir", "os.link", "os.symlink"}:
            raise RuntimeError("Demo filesystem mutation prohibited")
    sys.addaudithook(audit)
    socket.socket.connect = deny
    socket.socket.sendto = deny
    socket.create_connection = deny
    # Replace only this Python process's mapping; never inspect or change real values.
    os.environ = CredentialBlindEnvironment()
    _INSTALLED = True
