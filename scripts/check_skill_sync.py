from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_SKILL_DIR = ROOT / ".agents" / "skills" / "option-strategy-builder"
CLAUDE_SKILL_DIR = ROOT / ".claude" / "skills" / "option-strategy-builder"
CLAUDE_AGENT_FILE = ROOT / ".claude" / "agents" / "option-strategy-builder.md"
CODEX_SKILL_DIR = ROOT / ".codex" / "skills" / "build-option-strategy"

REFERENCE_FILES = (
    "architecture-patterns.md",
    "schema-and-persistence.md",
    "example-optionforge.md",
)

CORE_BANNED_TOKENS = (
    "OptionForge",
    "Codex",
    "src/strategy/",
    ".focus",
    "strategy_spec.toml",
    "vn.py",
)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def split_frontmatter(text: str) -> tuple[str, str]:
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if match is None:
        raise ValueError("markdown file must start with YAML frontmatter")
    return match.group(1), text[match.end():]


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def check_platform_neutral_core() -> None:
    for path in (
        CANONICAL_SKILL_DIR / "SKILL.md",
        CANONICAL_SKILL_DIR / "references" / "architecture-patterns.md",
        CANONICAL_SKILL_DIR / "references" / "schema-and-persistence.md",
    ):
        text = read_text(path)
        for token in CORE_BANNED_TOKENS:
            expect(token not in text, f"{token!r} leaked into {path}")


def check_optional_example() -> None:
    text = read_text(CANONICAL_SKILL_DIR / "references" / "example-optionforge.md")
    expect("optional example" in text.lower(), "example file must be marked optional")
    expect("OptionForge" in text, "example file should retain the concrete mapping")


def check_codex_adapter() -> None:
    canonical_frontmatter, canonical_body = split_frontmatter(
        read_text(CANONICAL_SKILL_DIR / "SKILL.md")
    )
    codex_frontmatter, codex_body = split_frontmatter(
        read_text(CODEX_SKILL_DIR / "SKILL.md")
    )
    expect(canonical_body == codex_body, "Codex body drifted from canonical skill")
    expect("name: option-strategy-builder" in canonical_frontmatter, "canonical name mismatch")
    expect("name: build-option-strategy" in codex_frontmatter, "Codex alias name mismatch")

    metadata = read_text(CODEX_SKILL_DIR / "agents" / "openai.yaml")
    for token in CORE_BANNED_TOKENS:
        expect(token not in metadata, f"{token!r} leaked into Codex metadata")


def check_claude_mirror() -> None:
    expect(
        read_text(CLAUDE_SKILL_DIR / "SKILL.md") == read_text(CANONICAL_SKILL_DIR / "SKILL.md"),
        "Claude skill mirror drifted from canonical skill",
    )

    for filename in REFERENCE_FILES:
        expect(
            read_text(CLAUDE_SKILL_DIR / "references" / filename)
            == read_text(CANONICAL_SKILL_DIR / "references" / filename),
            f"Claude reference drifted: {filename}",
        )

    frontmatter, body = split_frontmatter(read_text(CLAUDE_AGENT_FILE))
    expect("name: option-strategy-builder" in frontmatter, "Claude agent name mismatch")
    expect("skills:" in frontmatter, "Claude agent must declare skills")
    expect("option-strategy-builder" in frontmatter, "Claude agent must reference the skill")
    expect(
        "Use the `option-strategy-builder` skill" in body,
        "Claude wrapper should instruct use of the canonical skill",
    )


def check_codex_reference_mirror() -> None:
    for filename in REFERENCE_FILES:
        expect(
            read_text(CODEX_SKILL_DIR / "references" / filename)
            == read_text(CANONICAL_SKILL_DIR / "references" / filename),
            f"Codex reference drifted: {filename}",
        )


def main() -> int:
    check_platform_neutral_core()
    check_optional_example()
    check_codex_adapter()
    check_claude_mirror()
    check_codex_reference_mirror()
    print("Skill sync check passed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover
        print(f"Skill sync check failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
