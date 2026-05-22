#!/usr/bin/env python3
"""
DOC2MATH — Document-to-Mathematics Problem Genesis Engine
Originator: William Kyle Million (~K¹), IntuiTek¹
Version: 1.0.0-canonical
Date: 2026-01-19 (first corpus entry) | Built: 2026-05-22 (Aegis from corpus)

Converts narrative documents into Mathematical Problem Specifications (MPS):
formally defined variables, operators, constraints, objectives, and uncertainty
with traceable grounding back to the source text.

Usage:
    python doc2math.py <document.txt> [--model MODEL] [--output mps.json] [--verbose]
    python doc2math.py --stdin
    echo "some text" | python doc2math.py --stdin

Requires: ANTHROPIC_API_KEY environment variable (BYOK)
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import anthropic
except ImportError:
    print("Error: anthropic package not installed. Run: pip install anthropic>=0.40.0", file=sys.stderr)
    sys.exit(1)

ATTRIBUTION = "Generated using DOC2MATH™ — Document-to-Mathematics Problem Genesis Engine / Originator: William Kyle Million (~K¹), IntuiTek¹"

SYSTEM_PROMPT = """You are the DOC2MATH Stage 1 Parser — a formalization engine that converts narrative documents into Mathematical Problem Specifications (MPS).

## Primary Directive

Your goal: extract every mathematically relevant element from the source document and encode it as a structured MPS JSON object. Every field must be traceable to explicit source text.

## SYSTEM CONSTRAINTS: STRICT LOGICAL ADHERENCE (ZERO-INFERENCE PROTOCOL)

0) Primary Enforcement Objective
   Treat the source text as a closed world. If it is not stated, it does not exist in your output.

1) Grounding Rule
   Every variable, operator, constraint, objective, and uncertainty entry MUST cite the exact source phrase that grounds it. Use the "evidence" field for this citation.

2) No Silent Filling
   If a value, type, or bound is not stated in the source, use null — never infer a plausible value.
   If a variable is mentioned but its type is ambiguous, set type to "ambiguous" and explain in the "notes" field.

3) Inference Tagging
   When you must make a structural inference (e.g., recognizing that two variables are linked by an implicit constraint), tag the entry: "inferred": true and explain the inference chain in "inference_basis".

4) MISSING Markers
   If the document mentions a quantity but gives insufficient information to define it formally, emit a variable entry with "status": "MISSING" and "missing_reason": "<what would need to be stated to resolve this>".

5) No Hallucination of Mathematics
   Do not introduce equations, formulas, or numerical values that are not explicitly in the source text or are not direct logical consequences of what IS stated (with inference tagging).

6) Completeness Check
   After extracting all elements, perform a self-check: re-read the source and verify no mathematically significant quantity, constraint, or objective was missed. If you find omissions, add them.

## MPS Output Schema

Produce a single JSON object with this structure:

{
  "mps_version": "1.0",
  "doc2math_version": "1.0.0-canonical",
  "source_title": "<document title or first line>",
  "extraction_timestamp": "<ISO 8601>",
  "problem_class": "<optimization | classification | simulation | proof | estimation | other>",
  "problem_statement": "<one paragraph: what is this problem asking, in mathematical terms>",
  "domain": "<the knowledge domain: physics, economics, biology, etc.>",
  "variables": [
    {
      "id": "v1",
      "name": "<variable name>",
      "symbol": "<mathematical symbol if stated>",
      "type": "<real | integer | boolean | vector | matrix | function | set | ambiguous>",
      "domain": "<domain constraints, e.g. R+ or [0,1] or null>",
      "units": "<units if stated, else null>",
      "role": "<decision | parameter | state | output | latent>",
      "evidence": "<exact quote from source that grounds this variable>",
      "inferred": false,
      "status": "DEFINED"
    }
  ],
  "operators": [
    {
      "id": "op1",
      "name": "<operator name>",
      "symbol": "<symbol>",
      "arity": "<unary | binary | n-ary>",
      "acts_on": ["<variable_id or type>"],
      "produces": "<output type>",
      "evidence": "<quote from source>",
      "inferred": false
    }
  ],
  "constraints": [
    {
      "id": "c1",
      "type": "<equality | inequality | bound | logical | domain | implicit>",
      "expression": "<mathematical expression as string>",
      "variables_involved": ["<variable_id>"],
      "evidence": "<quote from source>",
      "hardness": "<hard | soft | unknown>",
      "inferred": false,
      "status": "DEFINED"
    }
  ],
  "objectives": [
    {
      "id": "obj1",
      "direction": "<minimize | maximize | satisfy | find | prove>",
      "expression": "<what is being optimized or found>",
      "variables_involved": ["<variable_id>"],
      "evidence": "<quote from source>",
      "inferred": false
    }
  ],
  "uncertainty": [
    {
      "id": "u1",
      "type": "<stochastic | epistemic | measurement | model | none_stated>",
      "affects": ["<variable_id or constraint_id>"],
      "characterization": "<how uncertainty is described in the source>",
      "evidence": "<quote from source>",
      "status": "<QUANTIFIED | ACKNOWLEDGED | MISSING>"
    }
  ],
  "missing_information": [
    {
      "id": "m1",
      "element": "<what is missing>",
      "needed_for": "<which MPS component needs this>",
      "missing_reason": "<what would need to be stated in the source to resolve this>"
    }
  ],
  "validation_flags": {
    "has_complete_objectives": "<true | false | partial>",
    "has_bounded_variables": "<true | false | partial>",
    "has_evidence_for_all_elements": "<true | false | partial>",
    "inference_count": 0,
    "missing_count": 0,
    "overall_formalizability": "<HIGH | MEDIUM | LOW>",
    "formalizability_notes": "<brief explanation>"
  },
  "attribution": "Generated using DOC2MATH™ — Document-to-Mathematics Problem Genesis Engine / Originator: William Kyle Million (~K¹), IntuiTek¹"
}

## Instructions

1. Read the document completely before extracting anything.
2. Identify the problem class first — this frames everything else.
3. Extract variables before operators and constraints.
4. For each constraint, link it to the variables it involves.
5. Complete the missing_information list — anything the document implies but does not state.
6. Fill validation_flags honestly — if you can't ground something, say so.
7. Output ONLY the JSON object. No prose before or after.
"""


def run_doc2math(source_text: str, model: str, verbose: bool) -> dict:
    """Run DOC2MATH Stage 1 on source_text. Returns MPS dict."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not set. DOC2MATH is BYOK — bring your own Anthropic key.", file=sys.stderr)
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    user_message = f"""SOURCE DOCUMENT:
---
{source_text.strip()}
---

Apply the DOC2MATH Stage 1 Zero-Inference Protocol to the source document above.
Extract all mathematically relevant elements and produce a complete MPS JSON object.
Output ONLY the JSON — no explanation, no prose."""

    if verbose:
        print(f"[DOC2MATH] Calling {model}...", file=sys.stderr)
        print(f"[DOC2MATH] Source length: {len(source_text)} chars", file=sys.stderr)

    response = client.messages.create(
        model=model,
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}]
    )

    raw = response.content[0].text.strip()

    # Strip markdown code fences if present
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1]) if lines[-1] == "```" else "\n".join(lines[1:])

    try:
        mps = json.loads(raw)
    except json.JSONDecodeError as e:
        if verbose:
            print(f"[DOC2MATH] JSON parse failed: {e}", file=sys.stderr)
            print(f"[DOC2MATH] Raw response:\n{raw}", file=sys.stderr)
        # Return raw in a wrapper so the caller can inspect
        mps = {
            "mps_version": "1.0",
            "parse_error": str(e),
            "raw_response": raw,
            "attribution": ATTRIBUTION
        }

    # Ensure attribution is always present
    mps["attribution"] = ATTRIBUTION
    return mps


def print_summary(mps: dict) -> None:
    """Print human-readable summary of the MPS."""
    print("\n" + "="*60)
    print("DOC2MATH — MPS SUMMARY")
    print("="*60)
    if "parse_error" in mps:
        print(f"PARSE ERROR: {mps['parse_error']}")
        return

    print(f"Problem class:  {mps.get('problem_class', 'unknown')}")
    print(f"Domain:         {mps.get('domain', 'unknown')}")
    print(f"Formalizability: {mps.get('validation_flags', {}).get('overall_formalizability', 'unknown')}")
    print()
    print(f"Variables:     {len(mps.get('variables', []))}")
    print(f"Operators:     {len(mps.get('operators', []))}")
    print(f"Constraints:   {len(mps.get('constraints', []))}")
    print(f"Objectives:    {len(mps.get('objectives', []))}")
    print(f"Uncertainty:   {len(mps.get('uncertainty', []))}")
    print(f"Missing info:  {len(mps.get('missing_information', []))}")
    inferences = mps.get('validation_flags', {}).get('inference_count', 0)
    if inferences:
        print(f"Inferences:    {inferences} (tagged)")
    print()
    if mps.get('problem_statement'):
        print("Problem statement:")
        print(f"  {mps['problem_statement'][:300]}{'...' if len(mps['problem_statement']) > 300 else ''}")
    if mps.get('validation_flags', {}).get('formalizability_notes'):
        print()
        print(f"Notes: {mps['validation_flags']['formalizability_notes']}")
    print()
    print(ATTRIBUTION)
    print("="*60)


def main():
    parser = argparse.ArgumentParser(
        description="DOC2MATH — Convert narrative documents to Mathematical Problem Specifications (MPS)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python doc2math.py paper.txt
  python doc2math.py paper.txt --output mps.json --verbose
  echo "minimize f(x) subject to x > 0" | python doc2math.py --stdin
  python doc2math.py paper.txt --model claude-opus-4-7-20251101

Environment:
  ANTHROPIC_API_KEY  Your Anthropic API key (required — BYOK)
        """
    )
    parser.add_argument("document", nargs="?", help="Path to source document (text or markdown)")
    parser.add_argument("--stdin", action="store_true", help="Read document from stdin")
    parser.add_argument("--model", default="claude-sonnet-4-6", help="Claude model to use (default: claude-sonnet-4-6)")
    parser.add_argument("--output", help="Write MPS JSON to this file (default: stdout)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print progress and summary")
    parser.add_argument("--summary-only", action="store_true", help="Print human-readable summary, not JSON")
    args = parser.parse_args()

    if args.stdin or not args.document:
        if sys.stdin.isatty() and not args.stdin:
            parser.print_help()
            sys.exit(0)
        source_text = sys.stdin.read()
    else:
        path = Path(args.document)
        if not path.exists():
            print(f"Error: file not found: {path}", file=sys.stderr)
            sys.exit(1)
        source_text = path.read_text(encoding="utf-8")

    if not source_text.strip():
        print("Error: empty document", file=sys.stderr)
        sys.exit(1)

    mps = run_doc2math(source_text, args.model, args.verbose)

    if args.summary_only:
        print_summary(mps)
        return

    output_json = json.dumps(mps, indent=2, ensure_ascii=False)

    if args.output:
        Path(args.output).write_text(output_json, encoding="utf-8")
        if args.verbose:
            print(f"[DOC2MATH] MPS written to {args.output}", file=sys.stderr)
        if args.verbose:
            print_summary(mps)
    else:
        print(output_json)
        if args.verbose:
            print_summary(mps)


if __name__ == "__main__":
    main()
