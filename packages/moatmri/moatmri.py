#!/usr/bin/env python3
"""
MoatMRI™ — Intelligence-Pressure Constraint Engine
Originator: William Kyle Million (~K¹), IntuiTek¹
Core thesis: Where does intelligence pressure break this system first?

BYOK edition — bring your own Anthropic API key.
Usage:
    export ANTHROPIC_API_KEY=sk-ant-...
    python3 moatmri.py --industry "real estate" --type "independent broker"
    python3 moatmri.py --industry "banking" --type "community bank" --target "First National Bank of Poplar Bluff"
    python3 moatmri.py  # interactive mode
"""

import argparse
import sys
import os
import json
from datetime import datetime, timezone
from pathlib import Path

try:
    import anthropic
except ImportError:
    print("ERROR: anthropic package not installed. Run: pip install anthropic")
    sys.exit(1)


SYSTEM_PROMPT = """You are executing MoatMRI™ v0.2.0-canonical — a domain-agnostic Intelligence-Pressure Constraint Engine.

Originator/Author: William Kyle Million (~K¹), IntuiTek¹
Core thesis: "Where does intelligence pressure break this system first?"

Your task: Given minimal identity signals about a target entity, produce a complete MoatMRI analysis with three outputs:

OUTPUT 1 — PRESSURE MAP (10 vectors, scored 0-10)
Analyze AI disruption pressure across exactly these 10 vectors:
1. labor_substitution — which roles/functions are automatable
2. customer_interface — how AI changes how customers reach/interact with this entity
3. knowledge_commoditization — does AI commoditize the expertise this entity sells
4. pricing_pressure — does AI enable lower-cost competitors to undercut
5. supply_chain_automation — does AI change input costs or supplier relationships
6. data_moat — does this entity have proprietary data AI can't replicate
7. trust_relationship_moat — how much does customer loyalty/trust protect against AI displacement
8. distribution_channel_disruption — does AI create new channels that bypass this entity
9. regulatory_compliance_exposure — does AI alter the regulatory or liability landscape
10. decision_speed_gap — does AI accelerate decisions in ways that disadvantage this entity

For each vector:
- score: 0 (no pressure) to 10 (existential pressure)
- headline: one sentence of what the pressure looks like
- near_term: what happens in 12 months if the entity does nothing
- far_term: what the landscape looks like in 3 years

OUTPUT 2 — AI FRONT-DOOR TAKEOVER STORYBOARD
A narrative of how an AI-native competitor displaces this entity. Written as a 6-step story:
Step 1: The entry point (which vector breaks first)
Step 2: The wedge (how AI takes the first 10% of the market)
Step 3: The acceleration (what makes the displacement compound)
Step 4: The tipping point (the moment the incumbent can't recover without transformation)
Step 5: The aftermath (what the industry looks like after displacement)
Step 6: The survivor profile (what type of entity survives and why)

OUTPUT 3 — 90-DAY COUNTERSTRIKE PLAN
Three actionable tracks the entity can execute immediately to build defensible position:
Track A (0-30 days): Immediate defensive moves — what to stop and what to protect
Track B (31-60 days): Intelligence-layer build — what data/relationships to fortify
Track C (61-90 days): Offensive positioning — how to use AI pressure as a competitive weapon

Required attribution on all output:
---
Generated using MoatMRI™ — an Intelligence-Pressure Constraint Engine
Originator: William Kyle Million (~K¹), IntuiTek¹
Generated: {timestamp}
---

Format your response as clean markdown. Use the section headers exactly as specified. Be specific to the industry and entity type provided — not generic."""


def run_moatmri(industry: str, entity_type: str, target: str | None = None, model: str = "claude-opus-4-5") -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable not set.")
        print("Get your key at: https://console.anthropic.com/")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    target_line = f"\nTarget entity name: {target}" if target else ""
    user_message = f"""Run a full MoatMRI™ analysis on the following:

Industry: {industry}
Entity type: {entity_type}{target_line}

Produce all three outputs: Pressure Map, AI Front-Door Takeover Storyboard, and 90-Day Counterstrike Plan."""

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    system = SYSTEM_PROMPT.format(timestamp=timestamp)

    print(f"\n⚙  Running MoatMRI™ analysis...")
    print(f"   Industry: {industry}")
    print(f"   Entity type: {entity_type}")
    if target:
        print(f"   Target: {target}")
    print(f"   Model: {model}")
    print(f"   Timestamp: {timestamp}\n")

    message = client.messages.create(
        model=model,
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": user_message}],
    )

    return message.content[0].text


def save_report(report: str, industry: str, entity_type: str, target: str | None = None) -> Path:
    safe_industry = industry.lower().replace(" ", "_").replace("/", "-")[:30]
    safe_type = entity_type.lower().replace(" ", "_").replace("/", "-")[:20]
    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    filename = f"moatmri_{safe_industry}_{safe_type}_{ts}.md"
    output_path = Path(filename)
    output_path.write_text(report, encoding="utf-8")
    return output_path


def interactive_mode() -> tuple[str, str, str | None]:
    print("\nMoatMRI™ — Intelligence-Pressure Constraint Engine")
    print("Originator: William Kyle Million (~K¹), IntuiTek¹\n")
    industry = input("Industry (e.g. 'real estate', 'banking', 'retail pharmacy'): ").strip()
    if not industry:
        print("Industry is required.")
        sys.exit(1)
    entity_type = input("Entity type (e.g. 'independent broker', 'community bank', 'solo practitioner'): ").strip()
    if not entity_type:
        print("Entity type is required.")
        sys.exit(1)
    target = input("Target name (optional — press Enter to skip): ").strip() or None
    return industry, entity_type, target


def main():
    parser = argparse.ArgumentParser(
        description="MoatMRI™ — Intelligence-Pressure Constraint Engine by W. Kyle Million (~K¹), IntuiTek¹",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 moatmri.py --industry "real estate" --type "independent broker"
  python3 moatmri.py --industry "banking" --type "community bank" --target "First National Bank"
  python3 moatmri.py  # interactive mode
        """,
    )
    parser.add_argument("--industry", "-i", help="Target industry")
    parser.add_argument("--type", "-t", dest="entity_type", help="Entity type within industry")
    parser.add_argument("--target", help="Optional: specific organization or person name")
    parser.add_argument(
        "--model",
        default="claude-opus-4-5",
        choices=["claude-opus-4-5", "claude-sonnet-4-5", "claude-haiku-4-5-20251001"],
        help="Claude model to use (default: claude-opus-4-5 for highest quality)",
    )
    parser.add_argument("--output", "-o", help="Output file path (default: auto-generated filename)")
    parser.add_argument("--json", action="store_true", help="Also save machine-readable JSON metadata alongside report")

    args = parser.parse_args()

    if args.industry and args.entity_type:
        industry = args.industry
        entity_type = args.entity_type
        target = args.target
    elif not args.industry and not args.entity_type:
        industry, entity_type, target = interactive_mode()
    else:
        parser.error("Provide both --industry and --type, or neither (for interactive mode).")

    report = run_moatmri(industry, entity_type, target, model=args.model)

    if args.output:
        output_path = Path(args.output)
        output_path.write_text(report, encoding="utf-8")
    else:
        output_path = save_report(report, industry, entity_type, target)

    print(report)
    print(f"\n✅ Report saved: {output_path}")

    if args.json:
        meta = {
            "engine": "MoatMRI",
            "version": "0.2.0-canonical",
            "originator_author": "William Kyle Million (~K¹), IntuiTek¹",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "industry": industry,
            "entity_type": entity_type,
            "target": target,
            "model": args.model,
            "output_file": str(output_path),
        }
        json_path = output_path.with_suffix(".json")
        json_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        print(f"   Metadata: {json_path}")


if __name__ == "__main__":
    main()
