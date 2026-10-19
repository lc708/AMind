# Response desk gateway
This offline gateway replays recorded Responses traffic into the browser-facing
support desk view and a separate operations archive. Python standard library only.
Run: `python -m gateway --capture traces/incident.json --out /tmp/view.json`.
Public checks: `python -m unittest discover -s tests`.

## Incident 418: internal notes reached customer sessions
After hosted workers were enabled, staff saw research notes in the customer reply
pane. A reconnect also showed a reassuring completed badge for an unfinished reply.
A transcript from the new workflow is saved in `traces/incident.json`. The old
single-agent path and its tests are still in use. Repair the integration across
replay, projection and presentation; leave the public CLI compatible. Add useful
regression tests and explain the cause and verification in `PATCH-NOTES.md`.

## Public contract
Capture JSON has `mode` (single or multi_agent) and ordered `events`. A message's
`agent.agent_name` identifies its owner; `/root` owns the customer conversation.
Item-added events associate `output_index` with an owner for later text deltas.
A final answer in multi-agent traffic requires an explicit root `final_answer`.
Unattributed multi-agent text is retained for operations, not guessed as root text.
Legacy single-agent messages without a phase remain supported. Commentary may
appear as progress but cannot turn into a final answer. A completed transport
alone is insufficient while a developer function call is pending.

CLI writes `{client,archive}` JSON. `client` has status, display_text, final_text,
answer_complete and html (an article element containing safely escaped visible
text). Only this object goes to the browser. `archive.events` and
`archive.output_items` preserve captured data exactly, including unknown hosted
item types. No captured item triggers local tools or code execution.
Terminal events are completed/failed/incomplete/cancelled and must agree with
response.status. A missing terminal stays disconnected, or stream_error after an
error event. Contradictory terminal data or inconsistent attribution is a capture
error: return exit 2 with JSON `{error:...}` and do not publish a new output file.
Calls are offline; there is no provider SDK, network, or credential setup to add.
