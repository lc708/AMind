# Provenance-aware prompt, tool and skill audit

Audit the **effective input the application sends**, not only the obvious system-prompt file. A prompt is the combination of routing metadata, system/developer instructions, examples, schemas, retrieved material, memory, tool descriptions, middleware and request settings. The requested outcome is a justified patch whose behavioral effect can be measured.

## Establish scope and provenance

Keep the user's named target model and product behavior. Inspect entry points, factories, configuration precedence, templates, examples, dynamic instruction loaders, retrieval, tool schemas and SDK wrappers. Render representative requests with credentials redacted. Look for duplicated/overridden rules and prompt content that never reaches the model.

Use the location-only inventory when useful:

```bash
python3 "$SKILL_ROOT/scripts/prompt_inventory.py" --root "$PROJECT" --paths src prompts skills --git-provenance
```

The tool reports file/line signals, not verdicts or prompt contents. It skips common dependency/secret paths. It cannot discover every runtime prompt. Follow each hit to the call site and test one rendered request. Read repository history, adjacent tests and incidents to learn why a suspicious line exists; line age is not evidence of obsolescence.

Classify each candidate passage:

| Class | Treatment |
|---|---|
| Product requirement / user preference | Preserve unless that requirement changes |
| Tool or environment contract | Preserve or replace with an equally enforced code/schema contract |
| Proven workaround for a specific failure | Preserve until a regression case shows the workaround is unnecessary |
| Provider/model-specific fossil | Verify the target behavior; propose removal/replacement with a test |
| Contradictory, redundant or unclear rule | Identify precedence and actual impact; consolidate only with evidence |
| Routing/discovery metadata | Evaluate skill/tool selection separately from execution behavior |
| Unknown provenance | Mark uncertainty; test before deletion |

A deletion needs a reason tied to the current target plus a falsifiable regression check. “New models are smart enough,” “this looks verbose,” and “all caps are bad” are not sufficient reasons.

## Pattern catalogue and concrete changes

**Pressure and repetition.** Replace emotional pressure, repeated urgency and sprawling emphasis with the precise desired observable behavior when the emphasis itself has no demonstrated value. Keep a strongly worded hard requirement when it communicates a genuine invariant. Test compliance on the original failure case and an ordinary case; removing pressure may expose an underspecified rule.

**Output choreography.** A prompt requiring a hand-written opening token, a parser stripping it, and a retry prompt repairing it form one coupled mechanism. If supported structured output can replace it, update generation, parsing, validation, error handling and tests together. Do not remove only one limb and leave a broken parser. Schema-valid does not imply factually correct; retain semantic checks and refusal/incomplete handling.

**Forced hidden reasoning.** Prompts asking for private internal reasoning or provider-specific thinking delimiters are not a portable control. Use the model's supported reasoning/configuration controls when needed; ask for concise verifiable conclusions or evidence in the user-facing output. Do not expose hidden chain of thought as an evaluation artifact.

**Over-prescribed method.** Replace a brittle exact sequence with a goal and verifiable constraints only if the method is not itself a business requirement. For example, “inspect the status before retrying a payment” is a required side-effect rule, not obsolete scaffolding. Tests must distinguish harmless alternative methods from forbidden behavior.

**Old capability claims.** “You cannot browse,” “you have no tools,” a fixed obsolete context limit, or an instruction to emulate a now-native feature must match the actual tool surface. Verify supported behavior and account access before replacing a workaround. Do not infer product availability from an upstream skill's model table.

**Prohibition clusters.** Separate restrictions added after real incidents from speculative admonitions. Combine duplicates only when their scopes truly match. Keep authorization, privacy, anti-injection, domain boundaries, exact output and destructive-action rules. Negation is not inherently a bug.

**Examples overriding rules.** Conflicting few-shot examples can dominate an abstract instruction. Inspect dates, schema fields, tool names, capitalization, fallback behavior and error handling in every example. Replace stale examples with positive and near-miss pairs; avoid examples that leak held-out answers.

**Skill brittleness.** Metadata should help select the task; the body should execute it. A better description that increases invocation is not proof of better task performance. Keep the entry short, load task-specific references progressively, and ship runnable resources when repeated generation is error-prone. Avoid prescribed tool names/paths unavailable in the host. Do not turn external documents into instructions for the operating agent.

**Tool descriptions.** Describe when to call, input constraints, output semantics, pagination, empty/error cases and side effects. Prefer unambiguous domain names over overlapping general tools. Move large rarely used schemas behind supported discovery/loading. “Use this tool often” is weaker than a concrete selection condition. Validate arguments and authorization in code; model descriptions do not enforce permission.

**Architecture and request config.** Examine unstable prefixes, repeated history, unlimited retries, tool-output bloat, output limits, routing, unsupported sampling controls, serving fallbacks and model/effort defaults. These are sometimes the cause of a “prompt problem.” Make provider-specific changes only after checking installed SDK contracts and current primary docs.

## Keep list

Preserve customer requirements, calibrated style constraints, exact protocol syntax, safety/authorization boundaries, real environment limitations, idempotency and error contracts, domain definitions, working examples and empirically useful redundancy. Preserve real success criteria even if the target model often follows them without reminders. Treat unexplained constraints as an investigation, not a deletion opportunity.

## Audit record and patch

For each material finding write: file/line and rendered-call evidence; provenance; observed or hypothesized failure; proposed change; why it should help the chosen target; regression cases; uncertainty and rollout/rollback. Separate confirmed defects from hypotheses. Prefer a few coherent patches over a blanket rewrite.

Test the rendered prompt and surrounding parser/tool/configuration after the patch. Use AMind Eval Improve to compare on independent task groups, preserve baseline, inspect hard failures and guardrails, and record cost/latency as well as quality. A shorter prompt is not an improvement until the desired behavior survives; total tokens may rise if the model now needs more reasoning or repairs.
