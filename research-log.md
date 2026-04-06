## 2026-04-05 Iteration 1
**Proposed:** Strengthen `agents/base/agent_runner.py` system instructions so each agent explicitly follows recall → plan → gather → verify → self-critique → finalize.
**Changed:** `agents/base/agent_runner.py`
**Result:** kept
**Reason:** Small prompt-only change that pushes the swarm closer to the autoresearch loop without changing endpoints or compose structure.

## 2026-04-05 Iteration 2
**Proposed:** Expose agent tool usage in live logs by publishing tool call/result events from `agents/base/agent_runner.py` and rendering them in `ui/src/components/LogStream.tsx`.
**Changed:** `agents/base/agent_runner.py`, `ui/src/components/LogStream.tsx`
**Result:** kept
**Reason:** Improves observability with a small diff and makes the swarm's search/fetch behavior visible during a run.


## 2026-04-06 Iteration 1
**Proposed:** Fix the tool-loop exhaustion path in `agents/base/agent_runner.py` so the final tool-use round is not executed twice before forcing a final summary.
**Changed:** `agents/base/agent_runner.py`
**Result:** kept
**Reason:** Syntax check passed, and this prevents duplicate search/fetch/memory side effects when the agent hits the max tool rounds.

## 2026-04-06 Iteration 2
**Proposed:** Apply the same max-tool-round fix to `backend/routers/chat.py` so chat agents do not replay the final tool-use round before composing a final answer.
**Changed:** `backend/routers/chat.py`
**Result:** kept
**Reason:** Syntax check passed, and it removes duplicate tool calls and duplicate memory writes from interactive chat sessions.

## 2026-04-06 Iteration 3
**Proposed:** Publish a `tool_limit_reached` event from `agents/base/agent_runner.py` and render it in `ui/src/components/LogStream.tsx` so forced final summaries are visible in the live event stream.
**Changed:** `agents/base/agent_runner.py`, `ui/src/components/LogStream.tsx`
**Result:** discarded
**Reason:** The required UI verification command failed because `npx tsc --noEmit` cannot run in this repo without TypeScript installed, so the UI change was not kept.
