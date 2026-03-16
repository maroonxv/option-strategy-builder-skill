# Option Strategy Builder Skill

![Public](https://img.shields.io/badge/visibility-public-brightgreen?style=flat-square)
![Skill](https://img.shields.io/badge/type-agent%20skill-0f766e?style=flat-square)
![Claude Code](https://img.shields.io/badge/Claude%20Code-supported-8A2BE2?style=flat-square)
![Codex](https://img.shields.io/badge/Codex-supported-111827?style=flat-square)
![Gemini](https://img.shields.io/badge/Gemini-supported-2563EB?style=flat-square)
![License](https://img.shields.io/badge/license-MIT-blue?style=flat-square)

Platform-neutral skill pack for building option trading strategy systems.

English-first with light Chinese context:
This repository packages one reusable option strategy skill, then exposes thin compatibility layers for Codex, Claude Code, and Gemini-compatible `.agents/skills` workflows.

## What It Helps With

- Option contract and chain schema modeling
- Market data and trade persistence design
- Gateway and broker integration boundaries
- Contract discovery, filtering, and ranking
- Pricing, greeks, and volatility workflows
- Signal generation, execution, risk, and hedging
- Replay, warm restart, and monitoring separation

## Design Principles

- One canonical source of truth
- Thin platform adapters
- Repo-neutral architecture guidance
- Optional project-specific example, not hard-coded assumptions

## Repository Layout

```text
.
|-- .agents/skills/option-strategy-builder/
|   |-- SKILL.md
|   `-- references/
|-- .claude/
|   |-- agents/option-strategy-builder.md
|   `-- skills/option-strategy-builder/
|-- .codex/skills/build-option-strategy/
|-- scripts/check_skill_sync.py
|-- LICENSE
`-- README.md
```

## Canonical Source

The canonical skill lives in:

` .agents/skills/option-strategy-builder/ `

Everything else is a compatibility wrapper or mirror:

- `.claude/skills/option-strategy-builder/` mirrors the canonical skill for Claude Code
- `.claude/agents/option-strategy-builder.md` is a thin Claude subagent wrapper
- `.codex/skills/build-option-strategy/` is the Codex-facing alias and UI metadata layer

## Compatibility

| Platform | Entry point | Notes |
| --- | --- | --- |
| Gemini / generic agent skills | `.agents/skills/option-strategy-builder/` | Canonical source |
| Claude Code | `.claude/skills/option-strategy-builder/` + `.claude/agents/option-strategy-builder.md` | Uses a thin subagent wrapper |
| Codex | `.codex/skills/build-option-strategy/` | Keeps Codex-compatible name and `openai.yaml` |

## Installation

### Gemini-compatible or generic agent environments

Copy this directory into your target repository:

```text
.agents/skills/option-strategy-builder/
```

### Claude Code

Copy both:

```text
.claude/skills/option-strategy-builder/
.claude/agents/option-strategy-builder.md
```

### Codex

Copy:

```text
.codex/skills/build-option-strategy/
```

## Example Prompts

- "Design a schema for option contracts, quotes, greeks, orders, trades, and restart snapshots."
- "Help me build contract filtering and ranking logic for weekly index options."
- "Design gateway boundaries for broker callbacks, order normalization, and replay-safe persistence."
- "Design CTP trade and market-data gateway connection, recovery, and cancel boundaries."
- "Implement a signal pipeline for volatility regime changes with structured decision output."

## References

Inside the canonical skill:

- `references/architecture-patterns.md`
- `references/ctp-gateway-connection-patterns.md`
- `references/schema-and-persistence.md`
- `references/postgresql-schema-patterns.md`
- `references/example-optionforge.md`

`ctp-gateway-connection-patterns.md` is an optional CTP appendix for trade and market-data session sequencing, recovery, and cancel identity guidance.
`postgresql-schema-patterns.md` is an optional PostgreSQL appendix for concrete physical schema patterns.
`example-optionforge.md` is intentionally optional. It is a mapping example, not the default mental model.

## Maintenance

Run the sync checker after updating the canonical skill or any platform mirror:

```powershell
python scripts/check_skill_sync.py
```

It validates:

- canonical skill remains platform-neutral
- Claude and Codex mirrors stay in sync
- Codex metadata remains generic
- the optional example stays optional and repo-specific

## Notes

- The skill content is ASCII-first for validator and Windows locale compatibility.
- The public repo is intended to be copied into other repositories, not installed as a Python package.
- If you want to customize terminology for a specific broker or framework, keep those changes in your target repo instead of changing the canonical core unless the pattern is broadly reusable.
