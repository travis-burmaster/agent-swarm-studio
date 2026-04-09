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
## 2026-04-07 Iteration 1
**Proposed:** Strengthen `backend/routers/chat.py` so direct agent chats follow the same recall → plan → gather → verify → self-critique loop used by the background runner.
**Changed:** `backend/routers/chat.py`
**Result:** kept
**Reason:** Prompt-only change, syntax check passed, and it should improve chat quality/consistency without changing endpoints.

## 2026-04-07 Iteration 2
**Proposed:** Add explicit Anthropic credential validation in `backend/routers/chat.py` and `backend/routers/workflow.py` so missing API/proxy config fails fast with a clear message instead of opaque downstream errors.
**Changed:** `backend/routers/chat.py`, `backend/routers/workflow.py`
**Result:** kept
**Reason:** Concrete reliability/debuggability fix; syntax checks passed and the failure mode becomes much easier to diagnose.

## 2026-04-07 Iteration 3
**Proposed:** Improve `backend/routers/workflow.py` so timed-out workflows explicitly identify incomplete agents and tell the orchestrator synthesis step to acknowledge the missing coverage.
**Changed:** `backend/routers/workflow.py`
**Result:** kept
**Reason:** Small observability fix; syntax check passed and the final report should stop overclaiming completeness after timeouts.

## 2026-04-09 Iteration 1
**Proposed:** Release the Redis task lock in `agents/base/agent_runner.py` after each task finishes so retries and recovery are not blocked by a stale 10-minute lock.
**Changed:** `agents/base/agent_runner.py`
**Result:** kept
**Reason:** Syntax check passed, and this removes an avoidable reliability footgun in the task execution loop.
