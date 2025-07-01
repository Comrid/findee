import re
import subprocess
from pathlib import Path

VERSION_FILE = Path("findee/_version.py")

def read_version() -> str:
    text = VERSION_FILE.read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*"(\d+)\.(\d+)\.(\d+)"', text)
    if not match:
        raise ValueError("버전 정보를 찾을 수 없습니다.")
    return ".".join(match.groups())

def bump_patch_version(version: str) -> str:
    major, minor, patch = map(int, version.split("."))
    patch += 1
    return f"{major}.{minor}.{patch}"

def update_version_file(new_version: str):
    text = VERSION_FILE.read_text(encoding="utf-8")
    new_text = re.sub(
        r'__version__\s*=\s*"(\d+)\.(\d+)\.(\d+)"',
        f'__version__ = "{new_version}"',
        text
    )
    VERSION_FILE.write_text(new_text, encoding="utf-8")
    print(f"🔧 버전이 {new_version}으로 업데이트 되었습니다.")

def git_commit_push(new_version: str):
    cmds = [
        ["git", "add", "."],
        ["git", "commit", "-m", f"Updated in Version {new_version}"],
        ["git", "push", "origin", "main"]
    ]
    for cmd in cmds:
        print(f"$ {' '.join(cmd)}")
        subprocess.run(cmd, check=True)

if __name__ == "__main__":
    old_version = read_version()
    new_version = bump_patch_version(old_version)
    update_version_file(new_version)
    git_commit_push(new_version)