# MoatMRI™

**Intelligence-Pressure Constraint Engine**

> *"Where does intelligence pressure break this system first?"*
>
> — William Kyle Million (~K¹), IntuiTek¹

---

MoatMRI™ is a domain-agnostic AI disruption analysis engine. Given minimal inputs about a business (industry + entity type), it produces three outputs:

1. **Pressure Map** — 10-vector AI pressure analysis, scored and narrated
2. **AI Front-Door Takeover Storyboard** — a 6-step narrative of how an AI-native competitor displaces the entity
3. **90-Day Counterstrike Plan** — three tracks of actionable defensive and offensive moves

Built for consulting engagements, due diligence, and strategic planning. Every report carries attribution to the originator.

---

## BYOK Edition

This is the **Bring Your Own Key** edition. You supply the Anthropic API key; MoatMRI runs on your machine.

### Requirements

- Python 3.9+
- An [Anthropic API key](https://console.anthropic.com/)

### Install

```bash
pip install anthropic
```

### Run

```bash
# Set your API key
export ANTHROPIC_API_KEY=sk-ant-...

# Interactive mode
python3 moatmri.py

# CLI mode
python3 moatmri.py --industry "real estate" --type "independent broker"

# With a specific target
python3 moatmri.py --industry "banking" --type "community bank" --target "First National Bank of Springfield"

# Choose model (default: claude-opus-4-5 for highest quality)
python3 moatmri.py --industry "retail pharmacy" --type "independent pharmacy" --model claude-sonnet-4-5

# Save to a specific file
python3 moatmri.py --industry "law" --type "solo practitioner" --output my_report.md

# Also output machine-readable JSON metadata
python3 moatmri.py --industry "insurance" --type "independent agent" --json
```

### Output

Each run saves a markdown report to a timestamped file:
```
moatmri_real_estate_independent_20260118T034214.md
```

---

## What You Get

### Output 1 — Pressure Map

10 vectors, each scored 0–10:

| Vector | What it measures |
|---|---|
| `labor_substitution` | Which roles are automatable |
| `customer_interface` | How AI changes customer access |
| `knowledge_commoditization` | Whether expertise can be replicated by AI |
| `pricing_pressure` | AI-enabled low-cost competitor pressure |
| `supply_chain_automation` | Input cost changes via AI |
| `data_moat` | Proprietary data advantage |
| `trust_relationship_moat` | Loyalty/trust protection |
| `distribution_channel_disruption` | New channels that bypass the entity |
| `regulatory_compliance_exposure` | AI shifts in liability/regulatory landscape |
| `decision_speed_gap` | AI acceleration disadvantage for slow movers |

Each vector includes: score, headline, near-term impact (12 months), far-term impact (3 years).

### Output 2 — AI Front-Door Takeover Storyboard

A 6-step narrative: entry point → wedge → acceleration → tipping point → aftermath → survivor profile.

### Output 3 — 90-Day Counterstrike Plan

Three tracks: defensive moves (0–30 days), intelligence-layer build (31–60 days), offensive positioning (61–90 days).

---

## Attribution

All reports carry the required attribution footer:

```
Generated using MoatMRI™ — an Intelligence-Pressure Constraint Engine
Originator: William Kyle Million (~K¹), IntuiTek¹
```

This attribution is non-removable per the engine license. The MoatMRI™ methodology was originated by William Kyle Million in January 2026.

---

## Model Selection

| Model | Quality | Cost/report | Use for |
|---|---|---|---|
| `claude-opus-4-5` | Highest | ~$0.05–0.15 | Consulting deliverables, client-facing |
| `claude-sonnet-4-5` | High | ~$0.01–0.03 | Drafts, internal use |
| `claude-haiku-4-5-20251001` | Good | ~$0.001–0.003 | Bulk runs, screening |

---

## License

MoatMRI™ BYOK Edition — Personal and Commercial Use.

Attribution required: all generated reports must carry the MoatMRI™ attribution footer.
Originator: William Kyle Million (~K¹), IntuiTek¹ — 2026.

Questions / licensing: kyle@intuitek.ai
