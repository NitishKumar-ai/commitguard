import os
import stat
import sys
from pathlib import Path

PRE_COMMIT_SCRIPT = """#!/bin/sh
# CommitGuard pre-commit hook
echo "Running CommitGuard scan on staged changes..."
commitguard scan --staged --format text --fail-on-vulnerable
if [ $? -ne 0 ]; then
    echo "CommitGuard found vulnerabilities! Commit aborted."
    exit 1
fi
"""

PRE_PUSH_SCRIPT = """#!/bin/sh
# CommitGuard pre-push hook
echo "Running CommitGuard scan on commits to be pushed..."
while read local_ref local_sha remote_ref remote_sha
do
    if [ "$local_sha" != "0000000000000000000000000000000000000000" ]; then
        git diff "$remote_sha" "$local_sha" | commitguard scan --diff - --format text --fail-on-vulnerable
        if [ $? -ne 0 ]; then
            echo "CommitGuard found vulnerabilities in $local_sha! Push aborted."
            exit 1
        fi
    fi
done
"""

def install_hook(hook_type: str):
    git_dir = Path(".git")
    if not git_dir.exists() or not git_dir.is_dir():
        print("Error: .git directory not found. Please run this command from the root of a git repository.")
        sys.exit(1)

    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)

    hook_path = hooks_dir / hook_type
    script_content = PRE_COMMIT_SCRIPT if hook_type == "pre-commit" else PRE_PUSH_SCRIPT

    with open(hook_path, "w", encoding="utf-8") as f:
        f.write(script_content)

    # Make it executable
    st = os.stat(hook_path)
    os.chmod(hook_path, st.st_mode | stat.S_IEXEC)
    
    print(f"Successfully installed {hook_type} hook at {hook_path}")
