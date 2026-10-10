# Language-specific implementation and upgrade contracts

Use the repository's language and pinned dependency version. These recipes describe concrete integration points, not a claim that every language client supports every newly released feature. Official SDK status and snippets were checked against the [library guide](https://developers.openai.com/api/docs/libraries) on 2026-09-30; verify package source/types when implementing.

| Language | Client/source | Integration and upgrade checks |
|---|---|---|
| Python | `openai`, [openai-python](https://github.com/openai/openai-python) | `client.responses.create/parse`, `to_dict`, sync vs async clients, stream cleanup, retries/timeouts, Pydantic version and lockfile |
| TypeScript/JS | `openai`, [openai-node](https://github.com/openai/openai-node) | `client.responses.create/parse`, typed output unions, `toResponseInputItems` availability, `zodTextFormat`, AbortController, runtime fetch/stream behavior |
| Java | `com.openai:openai-java`, [openai-java](https://github.com/openai/openai-java) | Builder/union signatures, `client.responses().create`, nullable/optional variants, StreamResponse disposal, Maven/Gradle dependency resolution |
| Go | `github.com/openai/openai-go/v3`, [openai-go](https://github.com/openai/openai-go) | `client.Responses.New/NewStreaming`, typed input unions, context deadline/cancel, deferred stream Close, `stream.Err`, go.mod/go.sum |
| Ruby | `openai`, [openai-ruby](https://github.com/openai/openai-ruby) | `OpenAI::Client`, responses methods, keyword arguments, typed parsing support, enumerable stream lifetime, Gemfile.lock |
| C#/.NET | `OpenAI`, [openai-dotnet](https://github.com/openai/openai-dotnet) | `OpenAI.Responses.ResponsesClient`, async API/result types, SDK feature/experimental flags, CancellationToken, IDisposable/await foreach, NuGet lock |
| PHP | Existing HTTP transport or a verified community client | The official library directory lists community PHP clients; do not claim official SDK feature parity or invent namespaced methods |
| HTTP/cURL/CLI | REST reference; installed official `openai` CLI | Exact endpoint/body, headers, HTTP status, SSE parser, timeouts, stdin/file JSON and CLI `--help` |

## Representative calls

Python and TypeScript full response/tool/stream recipes are in [response recipes](response-recipes.md). Other language examples below are documentation fragments using caller-supplied `chosenModel` and `userInput`; add the product's error/status/usage handling rather than treating printed text as acceptance.

Java:

```java
ResponseCreateParams params = ResponseCreateParams.builder()
    .model(chosenModel).input(userInput).build();
Response response = client.responses().create(params);
response.output().stream()
    .flatMap(item -> item.message().stream())
    .flatMap(message -> message.content().stream())
    .flatMap(content -> content.outputText().stream())
    .forEach(text -> consumeText(text.text()));
// Persist the full response separately; this projection omits tools/refusal/state.
```

Go:

```go
ctx, cancel := context.WithTimeout(parentContext, taskTimeout)
defer cancel()
response, err := client.Responses.New(ctx, responses.ResponseNewParams{
    Model: chosenModel,
    Input: responses.ResponseNewParamsInputUnion{OfString: openai.String(userInput)},
})
if err != nil { return err }
consumeText(response.OutputText()) // Also inspect status/output/usage before accepting the task.
```

Ruby:

```ruby
response = client.responses.create(model: chosen_model, input: user_input)
persist_response(response.to_h)
consume_completed_response(response)
```

C#/.NET (check the installed SDK's exact overload and feature flags):

```csharp
ResponseResult response = await client.CreateResponseAsync(chosenModel, userInput);
ConsumeText(response.GetOutputText());
// Preserve full result and verify status/tool outcomes; do not suppress SDK warnings blindly.
```

PHP via an existing cURL transport can send the same REST body without guessing a community SDK method:

```php
$body = json_encode([
    'model' => $chosenModel,
    'input' => [['role' => 'user', 'content' => $userInput]],
], JSON_THROW_ON_ERROR);
curl_setopt_array($handle, [
    CURLOPT_POST => true,
    CURLOPT_POSTFIELDS => $body,
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_CONNECTTIMEOUT => 10,
    CURLOPT_TIMEOUT => $taskTimeoutSeconds,
]);
// The configured transport sets the trusted base URL and secret auth header.
// Check curl errors and HTTP status before json_decode(..., JSON_THROW_ON_ERROR).
```

HTTP uses `POST /v1/responses` with a JSON body shaped like `{model,input,...}` and configured authorization. Write JSON with a serializer and pass it as a file/stdin; do not interpolate task text into shell commands. Keep keys out of logs/command output. For SSE, parse event boundaries across network chunks; one chunk is not necessarily one JSON object. A browser-facing product keeps the secret client server-side.

The official `openai` CLI and `codex` CLI are separate tools. Inspect the chosen binary's version and subcommand help, use structured/file input, retain request status/usage, and implement process deadlines. A migration from an unrelated provider's CLI requires an explicit operation mapping; copying subcommand names is not a migration.

## Cross-language contract fixtures

Use identical serialized fixtures across language adapters: plain text; tool call and matching output; multiple calls; refusal; incomplete/token limit; malformed arguments; unknown output type retained; phase-bearing assistant item; opaque compaction; missing usage; transport/rate-limit failure; out-of-order batch result. Round-trip through the actual SDK serializer. Assert required fields survive and the application classifies each outcome identically.

Compile/type-check the languages actually changed. Dynamic-language smoke tests must exercise exact named parameters and result methods. Verify sync/async resource cleanup and cancellation, response body retention on errors, nested retries and pagination. Do not report eight-language runtime verification unless those compilers/runtimes and tests were actually run.

## Managed/runtime APIs

Managed agent methods and event types are separate from Responses. The current SDK family uses beta agent namespaces where supported; consult [agent lifecycle](agent-lifecycle.md) and exact installed types. Do not assume an Agents SDK session is a managed Agents API session or that a hosted sandbox implements application function handlers. When a client lacks a feature, a verified REST adapter or an explicit limitation is preferable to invented SDK calls.
