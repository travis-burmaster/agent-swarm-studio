## 2026-04-05 Iteration 1
**Proposed:** Strengthen `agents/base/agent_runner.py` system instructions so each agent explicitly follows recall → plan → gather → verify → self-critique → finalize.
**Changed:** `agents/base/agent_runner.py`
**Result:** kept
**Reason:** Small prompt-only change that pushes the swarm closer to the autoresearch loop without changing endpoints or compose structure.

