# Nuwa distillation method

Nuwa is AMind's internal evidence-to-advice method. It is not a public product name and does not imply private access.

## 1. Bound the corpus

Start from a declared public corpus. Preserve source, capture, manifestation, edition, and work as separate identities. Do not expand the corpus through ordinary citations, related links, navigation, or fuzzy title similarity.

## 2. Atomize claims

Turn source text into small propositions with exact quotes, epistemic force, speaker or institutional attribution, conditions, and stable evidence identifiers. A research agenda is not an answer; a forecast is not a fact.

## 3. Shape voices and versions

Keep institutional positions separate from named authors and speakers. Keep explicit revisions separate unless exact evidence proves the same edition. Use publication-time roles, not current roles projected backward.

## 4. Synthesize mechanisms

Move through this ladder:

```text
public evidence
  -> atomic claims
  -> repeated mechanisms
  -> stable habits of thought
  -> conditions and counterexamples
  -> advice for the user's situation
```

A stable habit needs repeated evidence or a clearly bounded institutional policy. Preserve disagreement and tension where the evidence does.

## 5. Stress-test the advice

Before answering, ask:

- Which premise carries the most uncertainty?
- What observable capability or harm threshold should change the response?
- Which defense could fail independently?
- What would a skeptical external evaluator demand?
- Are human agency, distribution, and institutional legitimacy represented?
- Is the recommendation reversible while evidence is weak?

The characteristic AMind move is not “be cautious.” It is to convert uncertainty into measurement, staged commitment, independent checks, and explicit escalation conditions.

## What 52,225 claims become

Nuwa does not squeeze the corpus into one large prompt or select a few excerpts and discard the rest. It produces two complementary outputs:

1. **A compact reasoning interface** — decision procedure, recurring mechanisms, bounded voice profiles, preserved tensions, attribution rules, and answer patterns.
2. **A retrievable evidence memory** — every atomic claim remains locally searchable and bound to its source passage, while a smaller reviewed set calibrates trust and evaluation.

In AMind, that package has this shape:

```text
SKILL.md                              decision procedure and boundaries
references/
  method.md                           construction and synthesis method
  evidence-policy.md                  attribution and evidence-distance rules
  retrieval.md                        recall, ranking, diversity, and verification
  answer-patterns.md                  output modes
data/
  amind-full-index.sqlite3            52,225 searchable atomic claims
  passages.jsonl.gz                   13,436 bound source passages
  evidence-kernel.jsonl               54 human-reviewed Gold rows
  theme-catalog.jsonl                 9 recurring lenses
  voice-profiles.jsonl                5 bounded voice syntheses
  synthesis-tensions.jsonl            5 preserved disagreements or tradeoffs
  manifest.json                       hashes, counts, provenance, and boundaries
scripts/
  query.py                            runtime retrieval and passage lookup
  verify.py                           self-contained integrity verification
evals/
  cases.jsonl                         reasoning and boundary cases
  retrieval-cases.jsonl               relevance, recency, and diversity cases
```

The 54 Gold rows are selected representatives, not the raw material from which the other 52,171 claims are inferred. Theme coverage, attribution, source identity, temporal scope, and equivalence auditing operate over the full population. At runtime, retrieval finds a small diverse candidate set, passage inspection establishes contextual support, and only then does the reasoning interface synthesize an answer.

## Nine recurring lenses

The skill's theme catalog contains the exact theses and representative evidence. In shorthand:

1. Alignment as hidden behavior
2. Capability scaling under uncertainty
3. Capability-triggered governance
4. Disciplined agent engineering
5. Economic transition and distribution
6. Human agency, values, and welfare
7. Measurement and adaptive evaluation
8. Mechanistic legibility
9. Security and defense in depth

Use only the lenses that illuminate the user's problem. Do not force every answer through all nine.
