import shutil
from pathlib import Path

CLAUDE_MD = Path.home() / ".claude" / "CLAUDE.md"
BOOTSTRAP = (Path(__file__).parent / "assets" / "claude-bootstrap.md").resolve()


def install_claude_bootstrap(bootstrap_path: Path = BOOTSTRAP, claude_md: Path = CLAUDE_MD) -> None:
    claude_md = Path(claude_md)
    bootstrap_path = Path(bootstrap_path).resolve()

    if claude_md.exists() and not claude_md.is_symlink():
        backup = claude_md.with_suffix(".md.bak")
        shutil.copy2(claude_md, backup)
        print(f"  backed up {claude_md} → {backup}")

    if claude_md.is_symlink():
        claude_md.unlink()

    claude_md.symlink_to(bootstrap_path)
    print(f"  {claude_md} → {bootstrap_path}")
