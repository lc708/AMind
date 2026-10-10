# Responses, output schemas, streaming and tools

These are destination-native documentation examples verified against official guides on 2026-09-30. Keep the application's configured client and chosen model. Check installed SDK signatures before applying them; examples have not made live API calls as part of this skill package.

## Basic request and outcome extraction

```python
response = client.responses.create(
    model=chosen_model,
    instructions=task_instructions,
    input=[{"role": "user", "content": user_input}],
    max_output_tokens=output_budget,
)
raw = response.to_dict()             # Retain complete output items and usage.
if response.status != "completed":
    handle_incomplete_or_failed(raw) # Preserve reason; do not pretend partial text is success.
else:
    consume_completed_response(raw)  # Inspect tool calls and refusals as well as text.
```

```typescript
const response = await client.responses.create({
  model: chosenModel,
  instructions: taskInstructions,
  input: [{ role: "user", content: userInput }],
  max_output_tokens: outputBudget,
});
await persistResponse(response);
if (response.status !== "completed") handleIncompleteOrFailed(response);
else consumeCompletedResponse(response);
```

`output` is a heterogeneous array. Do not assume the first item is final assistant text. `output_text` is a convenient text projection, not full state. Preserve message `phase`, tool calls, reasoning/compaction items, refusal content, status and usage. `scripts/response_contract.py` supplies offline tested normalization, terminal stream handling and batch result matching. It treats a refusal as an observable outcome for the task rubric, not automatically as an infrastructure failure.

The normalizer exposes `commentary_text`, `final_text` and `answer_complete` separately. Its legacy `text` field includes all text for display, while `scorable_transport` means only that the provider response completed. Neither proves product-task success. Pending function calls still require execution; preserve unknown phases in `output_items`. Batch HTTP success also needs the body outcome checked: the matcher retains `errors`, `incomplete`, `unknown_status` and missing IDs without discarding usage.

Preserve `raw_response` and `raw_events` for diagnosis, including partial usage observed before a disconnect. Partial counters are evidence, not a finalized total. A response that simultaneously declares completion and carries an error or non-null incomplete details is contradictory and must fail validation, including inside an HTTP-success batch row.

## Structured output

For text intended for a parser, use a supported JSON-schema format rather than a fragile opening-token trick. This schema encodes shape; verify factual/business constraints after parsing.

```python
schema = {
    "type": "object",
    "properties": {
        "category": {"type": "string", "enum": ["billing", "technical", "other"]},
        "customer_id": {"type": ["string", "null"]},
    },
    "required": ["category", "customer_id"],
    "additionalProperties": False,
}
response = client.responses.create(
    model=chosen_model,
    input=classification_input,
    text={"format": {"type": "json_schema", "name": "ticket", "schema": schema, "strict": True}},
)
```

Python's typed parsing helper uses `client.responses.parse(..., text_format=PydanticModel)`. TypeScript uses `client.responses.parse({... text:{format:zodTextFormat(Schema,"name")}})` from `openai/helpers/zod`. Check `status`, refusal content and parsed output availability before consuming it. Do not assume an interrupted/refused answer obeys the success schema. Strict schema subsets and model support must match current docs. Source: [structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs).

## Function tools and continuation

A function definition names the tool, its selection condition and parameters. For supported strict mode, objects use `additionalProperties:false`; required properties include nullable fields instead of pretending omitted and null are identical.

```json
{
  "type":"function",
  "name":"lookup_invoice",
  "description":"Read an invoice for the authenticated tenant by invoice ID.",
  "parameters":{
    "type":"object",
    "properties":{"invoice_id":{"type":"string"}},
    "required":["invoice_id"],
    "additionalProperties":false
  },
  "strict":true
}
```

The schema deliberately does not accept a tenant identifier from the model. Derive identity from the authenticated application context; validate the invoice ID and authorize that resource in the handler. A generated schema-valid call still can be unauthorized.

For client-managed Responses history:

```python
history = [{"role": "user", "content": user_input}]
response = client.responses.create(model=chosen_model, tools=tool_schemas, input=history)
history.extend(item.to_dict() for item in response.output)
for item in response.output:
    if item.type != "function_call":
        continue
    result = validated_authorized_dispatch(item.name, item.arguments, item.call_id)
    history.append({"type":"function_call_output", "call_id":item.call_id, "output":serialize_result(result)})
# Continue only within the registered round/call/deadline budget.
```

The full loop must handle zero/multiple calls, errors, refusal/incomplete state, cancellation, repeated IDs and idempotency. Use `tool_loop.py` as a reference or the project's existing framework. Preserve all output items instead of rebuilding history from text alone. In current TypeScript SDKs, `toResponseInputItems` from `openai/lib/responses/ResponseInputItems` performs typed conversion; verify that helper in the installed version. Source: [function calling](https://developers.openai.com/api/docs/guides/function-calling).

Parallel calls are appropriate only for independent operations with bounded concurrency. Disable or serialize them when mutations/order require it. Tool search/deferred loading, custom tools, namespaces and programmatic tool calling are separate capabilities with model/runtime support constraints; use the documented surface for the selected runtime, not a guessed shared field.

## Streaming

```python
stream = client.responses.create(model=chosen_model, input=user_input, stream=True)
try:
    for event in stream:
        if event.type == "response.output_text.delta":
            publish_provisional_text(event.delta)
        elif event.type in ("response.completed", "response.failed", "response.incomplete"):
            persist_terminal_response(event.response.to_dict())
        elif event.type == "error":
            record_stream_error(event)
finally:
    stream.close()
```

```typescript
const stream = await client.responses.create({ model: chosenModel, input: userInput, stream: true });
try {
  for await (const event of stream) {
    await ingestTypedEvent(event); // Deltas are provisional; terminal response owns result/usage.
  }
} finally {
  stream.controller.abort();
}
```

Track events by their item/output indices and IDs if assembling intermediate tools/content. Use final complete items where available. A stream that ends without a terminal outcome is disconnected, even if some text was displayed. Set an independent wall-clock deadline; keepalives must not defeat it. Closing a client stream does not necessarily cancel server work. Partial output may require separate presentation/content checks in the product. Source: [streaming responses](https://developers.openai.com/api/docs/guides/streaming-responses).

## Conversation and compaction

Choose client-managed history, `previous_response_id` chaining or a durable conversation/session. Do not combine their full histories inadvertently. Client-managed history preserves protocol items including supplied `phase`; chained requests send new input under the correct parent and current instruction/settings contract.

For explicit client compaction:

```python
compacted = client.responses.compact(model=chosen_model, input=history)
next_input = [*compacted.output, {"role":"user", "content":new_user_input}]
response = client.responses.create(model=chosen_model, input=next_input, store=False)
```

Treat compacted output as opaque supported state. Server-side `context_management` with a supported `compact_threshold` is another path; follow the current guide for the chosen model and storage policy. Do not manually prune a server-owned response chain. Test the first post-compaction tool and factual task. See [context diagnosis](context-state.md) and [compaction](https://developers.openai.com/api/docs/guides/compaction).

## Failure paths to implement

Malformed requests/schema/unsupported settings: fix the request, do not exponential-retry a permanent error. Auth/permission/availability: identify the affected account/resource and preserve secrets. Rate limit/overload/transient transport: bounded retry with jitter and Retry-After where appropriate. Timeout or lost response after a mutation: reconcile before retry. Truncation/refusal: preserve the outcome, decide using the task contract, and avoid silently changing providers/models to get a desired answer.

Record request IDs and all billable usage available even on failure. Keep retries at one intentional layer or account for multiplicative SDK/application retries. Test terminal statuses, final-item serialization, argument validation, authorization and result correspondence with fixtures before a bounded live smoke run.
