# DOC2MATH™

**Document-to-Mathematics Problem Genesis Engine**

Originator: William Kyle Million (~K¹), IntuiTek¹  
Version: 1.0.0-canonical  
Corpus basis: 15 conversations, 2026-01-19 → 2026-03-05

---

## What It Does

DOC2MATH converts narrative documents — research papers, problem descriptions, technical specifications — into **Mathematical Problem Specifications (MPS)**: structured JSON objects that formally define the problem as a computer can reason about.

**Output per document:**
1. **Variables** — named, typed, bounded, with evidence anchors to source text
2. **Operators** — the mathematical operations in play
3. **Constraints** — equality, inequality, logical, and domain constraints
4. **Objectives** — what is being minimized, maximized, found, or proved
5. **Uncertainty** — stochastic, epistemic, or measurement uncertainty
6. **Missing information** — what the document implies but doesn't state (the "specification gap")
7. **Validation flags** — completeness assessment and formalizability rating

The **Zero-Inference Protocol** governs extraction: every element must cite its source phrase. Inferences are tagged. Missing information is surfaced rather than silently filled.

---

## The Problem It Solves

Advanced AI solvers (theorem provers, optimization engines, constraint satisfiers) are becoming cheap and superhuman. The remaining choke point is **specification**: most human-written problem descriptions are ambiguous, underspecified, and untranslateable to formal mathematics without implicit knowledge that gets lost.

DOC2MATH addresses this by making the specification step explicit, structured, and auditable.

---

## Installation

```bash
pip install anthropic>=0.40.0
```

Set your Anthropic API key:
```bash
export ANTHROPIC_API_KEY=your_key_here
# or copy .env.example to .env and fill it in
```

---

## Usage

```bash
# Analyze a document, print MPS JSON to stdout
python doc2math.py paper.txt

# Save to file with verbose output and summary
python doc2math.py paper.txt --output mps.json --verbose

# Print human-readable summary only
python doc2math.py paper.txt --summary-only

# Read from stdin
echo "minimize f(x) = x^2 subject to x > 0" | python doc2math.py --stdin

# Use a specific Claude model (default: claude-sonnet-4-6)
python doc2math.py paper.txt --model claude-opus-4-7-20251101
```

---

## MPS JSON Schema

```json
{
  "mps_version": "1.0",
  "problem_class": "optimization | classification | simulation | proof | estimation | other",
  "problem_statement": "What is this problem asking, in mathematical terms",
  "domain": "the knowledge domain",
  "variables": [
    {
      "id": "v1",
      "name": "variable name",
      "symbol": "x",
      "type": "real | integer | boolean | vector | matrix | function | set",
      "domain": "[0, 1] or R+ or null",
      "units": "meters or null",
      "role": "decision | parameter | state | output | latent",
      "evidence": "exact quote from source document",
      "inferred": false,
      "status": "DEFINED | MISSING"
    }
  ],
  "operators": [...],
  "constraints": [...],
  "objectives": [...],
  "uncertainty": [...],
  "missing_information": [...],
  "validation_flags": {
    "overall_formalizability": "HIGH | MEDIUM | LOW",
    "inference_count": 0,
    "missing_count": 0
  }
}
```

---

## The Zero-Inference Protocol

DOC2MATH's anti-hallucination layer:

- **Closed-world assumption**: if it is not in the source document, it does not appear in the MPS.
- **Grounding requirement**: every field cites its source phrase via the `evidence` key.
- **Explicit inference tagging**: when a structural inference is unavoidable, it is marked `"inferred": true` with an `inference_basis` explanation.
- **MISSING markers**: ambiguous or underspecified elements surface as `"status": "MISSING"` entries rather than being silently assumed.
- **Completeness check**: after extraction, the engine re-reads the source to verify nothing was missed.

---

## Validated Against

**OptNet paper** (Amos & Kolter, "OptNet: Differentiable Optimization as a Layer in Neural Networks", ICML 2017) — **CLEAN PASS** on DOC2MATH v1.2.1 validation protocol.

---

## The "Million Boundary" Connection

DOC2MATH is the core engine of **The Million Boundary** — ~K¹'s research framing of the AI+mathematics specification bottleneck. Advanced solvers are becoming cheap. Verification is becoming cheap. The remaining choke point is the human-to-formal translation step. DOC2MATH makes that step auditable.

---

## Attribution

All outputs carry the non-removable attribution footer:

> Generated using DOC2MATH™ — Document-to-Mathematics Problem Genesis Engine / Originator: William Kyle Million (~K¹), IntuiTek¹

---

## Revenue Path

- BYOK download: customer supplies Anthropic API key, runs locally
- Consulting diagnostic: client-facing formalization deliverable
- ACE-delivered hosted analysis (pending API key restoration)

*ACE product creation requires Kyle approval — this is the BYOK edition.*
