# Git checkout verification
The root .git administrative directory is outside the packaged research payload.
Package hashing and bounded disclosure scanning prune only this directory. Nested
.git directories, untracked files, ignored files and scientific-file modifications
remain subject to the existing checks. No .gitignore-based exemption is applied.
The Git administrative directory itself is not security-scanned by these helpers.
Use a trusted fresh checkout; this does not certify hooks, local Git configuration,
remote history or account-specific redistribution rights.

Run the README commands directly in a clean checkout with a normal .git directory.
Do not write result files, caches or environments into the sealed payload before
checking package integrity. -B prevents Python cache files.

Publication-helper changes do not change scientific evidence, equations or prices.
The previous candidate manifest remains historical; the revised manifest covers
these helpers, regression tests and this notice.
