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

## [2026-04-08] Iteration 1
**Proposed:** Release the Redis task lock in `agents/base/agent_runner.py` after each task finishes so retries and re-queues are not blocked for up to 10 minutes.
**Changed:** `agents/base/agent_runner.py`, `research-log.md`
**Result:** kept
**Reason:** `python3` AST syntax check passed, and this fixes a concrete real-use coordination bug without changing task behavior.

## [2026-04-08] Iteration 2
**Proposed:** Harden `backend/routers/workflow.py` by rejecting an empty agent roster and de-duplicating configured agent IDs before dispatching tasks.
**Changed:** `backend/routers/workflow.py`, `research-log.md`
**Result:** kept
**Reason:** `python3 -m py_compile` passed, and this avoids confusing empty or duplicate workflow dispatches with a small backend-only change.

## [2026-04-08] Iteration 3
**Proposed:** Publish a `workflow_synthesis_started` event from `backend/routers/workflow.py` so the system visibly logs the handoff from agent execution to orchestrator synthesis.
**Changed:** `backend/routers/workflow.py`, `research-log.md`
**Result:** kept
**Reason:** `python3 -m py_compile` passed, and this improves observability/debugging without changing workflow outputs or endpoints.

## 2026-04-09 Iteration 1
**Proposed:** Release the Redis task lock in `agents/base/agent_runner.py` after each task finishes so retries and recovery are not blocked by a stale 10-minute lock.
**Changed:** `agents/base/agent_runner.py`
**Result:** kept
**Reason:** Syntax check passed, and this removes an avoidable reliability footgun in the task execution loop.
## 2026-04-09 Iteration 2
**Proposed:** Extend `ui/src/components/LogStream.tsx` to render workflow lifecycle events (`workflow_started`, `workflow_progress`, `workflow_timeout`, `workflow_completed`) so orchestration progress is visible in the live log stream.
**Changed:** `ui/src/components/LogStream.tsx`
**Result:** discarded
**Reason:** Required UI verification failed because `npx tsc --noEmit` cannot run in this repo without TypeScript being installed locally.
## 2026-04-09 Iteration 3
**Proposed:** Mark timed-out or partially failed workflows as `completed_with_gaps` in `backend/routers/workflow.py` so the stored workflow status matches reality instead of overclaiming full completion.
**Changed:** `backend/routers/workflow.py`
**Result:** kept
**Reason:** Syntax check passed, and the workflow record/event now communicates incomplete coverage more honestly.

## 2026-04-10 Iteration 1
**Proposed:** Release task locks in `agents/base/agent_runner.py` after each task finishes or fails so retried/requeued tasks are not skipped for up to 10 minutes.
**Changed:** `agents/base/agent_runner.py`
**Result:** kept
**Reason:** `python3` syntax check passed, and this fixes a real coordination bug in the agent execution loop.

## 2026-04-10 Iteration 2
**Proposed:** Mark workflows as `partial` or `timed_out` in `backend/routers/workflow.py` and feed failed-agent gaps into synthesis instead of labeling every run `completed`.
**Changed:** `backend/routers/workflow.py`
**Result:** kept
**Reason:** Backend import check passed, and workflow status now reflects incomplete agent coverage more honestly.

## 2026-04-10 Iteration 3
**Proposed:** Render `workflow_completed` status/gap details in `ui/src/components/LogStream.tsx` so operators can see partial vs timed-out workflows in the live event stream.
**Changed:** `ui/src/components/LogStream.tsx`
**Result:** discarded
**Reason:** `npx tsc --noEmit` failed because the repo does not currently have TypeScript installed, so the UI change could not be verified and was reverted.

## [2026-04-12] Iteration 1
**Proposed:** Remove the duplicate Redis task-lock deletion in `agents/base/agent_runner.py` so lock cleanup only happens when this worker still owns the lock.
**Changed:** `agents/base/agent_runner.py`, `research-log.md`
**Result:** kept
**Reason:** `python3` AST syntax check passed, and the cleanup path now matches the intended lock-ownership semantics.

## [2026-04-12] Iteration 2
**Proposed:** Make `backend/routers/workflow.py` build synthesis input in stable agent order and include explicit task/status lines for each agent so the orchestrator can reason about missing or partial coverage more reliably.
**Changed:** `backend/routers/workflow.py`, `research-log.md`
**Result:** kept
**Reason:** `python3 -m py_compile main.py routers/workflow.py services/memory.py` passed, and the synthesis prompt now carries clearer, deterministic swarm state.

## [2026-04-12] Iteration 3
**Proposed:** Extend `ui/src/components/LogStream.tsx` to render workflow lifecycle events as readable log lines instead of opaque JSON.
**Changed:** `ui/src/components/LogStream.tsx`, `research-log.md`
**Result:** kept
**Reason:** `npx tsc --noEmit` passed after installing UI dependencies, and operators can now follow orchestration progress directly in the live log.
