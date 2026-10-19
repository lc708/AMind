# Evidence policy

AMind is valuable only if it separates what the public record says from what the adviser infers.

## Three evidence-distance labels

### [Public position]

Use only when a source directly supports the material statement. Cite the source title, canonical URL, date when present, and claim ID. Quote sparingly and exactly.

### [Strong framework inference]

Use for a recurring mechanism reconstructed across multiple works or a clearly bounded institutional policy. Cite at least two independent evidence rows when practical. State the bridge from evidence to inference.

Two claim IDs from one experiment do not establish a recurring framework. Restatements of that experiment's findings or explicitly stated limits remain **[Public position]**. An additional interpretation beyond those statements needs cross-work support or an **[Exploratory extrapolation]** label; confidence in the interpretation alone does not make it a strong framework inference.

### [Exploratory extrapolation]

Use for a new case without exact precedent. Make the recommendation useful, then name the public principles being extended and the assumptions doing the work.

## Attribution rules

- “Anthropic” means a source-native institutional voice, not every employee or cofounder.
- A named person's public statement is not automatically Anthropic policy.
- A source that quotes a person is not authored by that person.
- A question, proposal, or research agenda is not an endorsed conclusion.
- Current job titles do not prove historical affiliation.
- Frequency measures corpus coverage, not consensus or influence.

## Citation contract

For a source-dependent claim, include:

- source title;
- publication date if the row supplies one;
- canonical URL;
- stable claim ID;
- exact quote only when it materially improves verification.

Never invent missing metadata. If a source date is unavailable, omit it or say “date unavailable.”

## Gold kernel versus full index

The installed skill contains two evidence tiers:

- **Gold kernel:** 54 evidence rows, six representatives for each of nine themes, individually reviewed in full passage context.
- **Full local index:** the complete source-linked claim corpus (exact counts and observation cutoff are in `data/manifest.json`), structurally and attribution audited but not individually human reviewed. The bound passages are bundled for local context inspection.

Use the full index for recall and the gold kernel for calibration. A full-index hit becomes suitable evidence only after checking its attribution class, epistemic force, conditions, source identity, and bound passage. Do not describe all indexed rows as human reviewed.

## Silence and conflicts

Before treating bounded evidence as silent, check relevant broader retrieval scopes with `--include-reported`, `--include-agenda`, and (for experimental model behavior) `--include-simulated`. Preserve those rows as reported positions or research questions rather than upgrading them to source beliefs or answers.

If no answer-eligible evidence remains within the attribution and agenda scopes searched:

1. State the scopes searched and say the bounded evidence is silent.
2. Do not call the absence a negative position.
3. Offer an exploratory extrapolation if it is useful.
4. Identify what evidence would upgrade or reverse it.

When sources pull in different directions, preserve the conditional tension. The tension catalog records five recurring examples; it is a navigation aid, not a substitute for source citations.

## Dated eligibility and corrections

Check each result's `current_status` before treating it as a current position. A correction can affect one provisional explanation without invalidating every observation in its article. Preserve original propositions, quotes, hashes and IDs; bind a separate dated correction or effective window to explicit claims or editions. Newer editions do not silently erase old evidence.

The default eligibility date is the source-observation cutoff. An `--as-of` date is a reconstruction from the recorded editions and date evidence, not a complete historical web snapshot. Month-only or unknown publication dates remain uncertain. After the collection cutoff, current verification is required even when a previously announced transition date is known.

Announcements and effective rules are separate: the October 8 usage-policy announcement is evidence available in October, while the new substantive rules take effect November 12. Guest posts and staff expectations keep their named/participant attribution. Repeated blog, PDF and summary carriers do not provide independent corroboration.
