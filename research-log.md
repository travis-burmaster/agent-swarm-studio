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

