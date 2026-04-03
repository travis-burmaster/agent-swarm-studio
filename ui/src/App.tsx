import React, { useState, useEffect } from "react";
import { Agent, Task, startAnalysis, askAllAgents, getConfig, restoreAgent } from "./lib/api";
import { useAgents } from "./hooks/useAgents";
import { useTasks } from "./hooks/useTasks";
import AgentBoard from "./components/AgentBoard";
import TaskPanel from "./components/TaskPanel";
import { ChatDrawer } from "./components/ChatDrawer";
import { LogStream } from "./components/LogStream";
import ReplaceAgentModal from "./components/ReplaceAgentModal";

export default function App() {
  const { agents, refresh: refreshAgents } = useAgents();
  const { tasks, submit, remove, refresh: refreshTasks } = useTasks();
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const [analyzeUrl, setAnalyzeUrl] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [showSynthesis, setShowSynthesis] = useState<Task | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [replaceTarget, setReplaceTarget] = useState<Agent | null>(null);

  // Prepopulate URL from backend config
  useEffect(() => {
    getConfig().then((cfg) => {
      if (cfg.target_company_url) setAnalyzeUrl(cfg.target_company_url);
    }).catch(() => {});
  }, []);

  const pendingCount = tasks.filter((t) => t.status === "pending" || t.status === "in_progress").length;
  const activeAgents = agents.filter((a) => a.status !== "offline").length;

  // Find the latest orchestrator synthesis
  const latestSynthesis = tasks.find(
    (t) => t.assign_to === "orchestrator" && t.status === "completed" && t.result
  );

  const handleAnalyze = async () => {
    const url = analyzeUrl.trim();
    if (!url || analyzing) return;
    setAnalyzing(true);
    try {
      await startAnalysis(url);
      setTimeout(refreshTasks, 1000);
    } catch (err) {
      console.error("Analysis failed:", err);
    } finally {
      setAnalyzing(false);
    }
  };

  const handleAskAll = async () => {
    const q = question.trim();
    if (!q || asking) return;
    setAsking(true);
    try {
      await askAllAgents(q, analyzeUrl.trim() || undefined);
      setQuestion("");
      setTimeout(refreshTasks, 1000);
    } catch (err) {
      console.error("Question dispatch failed:", err);
    } finally {
      setAsking(false);
    }
  };

  const handleRestore = async (agentId: string) => {
    if (!confirm(`Restore the original agent for slot "${agentId}"?`)) return;
    try {
      await restoreAgent(agentId);
      await refreshAgents();
    } catch (err) {
      console.error("Restore failed:", err);
    }
  };

  return (
    <div className="h-screen bg-surface flex flex-col overflow-hidden">
      {/* Header */}
      <header className="border-b border-border px-6 py-3 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <span className="text-2xl">🤖</span>
          <div>
            <h1 className="text-white font-bold text-base leading-tight tracking-tight">
              Agent Swarm Studio
            </h1>
            <p className="text-muted text-xs">Visual AI orchestration platform</p>
          </div>
        </div>
        <div className="flex items-center gap-4 text-sm">
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-green-500 inline-block" />
            <span className="text-gray-400">
              {activeAgents} agent{activeAgents !== 1 ? "s" : ""} online
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-yellow-400 inline-block" />
            <span className="text-gray-400">
              {pendingCount} task{pendingCount !== 1 ? "s" : ""} pending
            </span>
          </div>
          {latestSynthesis && (
            <button
              onClick={() => setShowSynthesis(showSynthesis ? null : latestSynthesis)}
              className="bg-emerald-700 hover:bg-emerald-600 text-white text-xs font-medium px-3 py-1 rounded-md transition-colors"
            >
              {showSynthesis ? "Hide Summary" : "View Summary"}
            </button>
          )}
          <button
            onClick={async () => {
              setRefreshing(true);
              await Promise.all([refreshAgents(), refreshTasks()]);
              setRefreshing(false);
            }}
            disabled={refreshing}
            className="text-muted hover:text-white text-xs px-2 py-1 border border-border rounded-md transition-colors disabled:opacity-50"
            title="Refresh"
          >
            {refreshing ? (
              <span className="flex items-center gap-1">
                <span className="w-2.5 h-2.5 border border-white/30 border-t-white rounded-full animate-spin" />
                Refreshing...
              </span>
            ) : (
              "↻ Refresh"
            )}
          </button>
        </div>
      </header>

      {/* Ask all agents bar */}
      <div className="border-b border-border px-6 py-2.5 flex items-center gap-3 bg-card/50">
        <label className="text-xs text-muted uppercase tracking-wide shrink-0">Ask Swarm</label>
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") handleAskAll(); }}
          placeholder="Ask all agents a question..."
          className="flex-1 bg-black/40 border border-border rounded-lg px-3 py-1.5 text-sm text-white placeholder-muted focus:outline-none focus:border-indigo-500 transition-colors"
        />
        <button
          onClick={handleAskAll}
          disabled={asking || !question.trim()}
          className="bg-purple-600 hover:bg-purple-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium px-4 py-1.5 rounded-lg transition-colors flex items-center gap-2"
        >
          {asking ? (
            <>
              <span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              Dispatching...
            </>
          ) : (
            "Ask All Agents"
          )}
        </button>
        <span className="text-[10px] text-muted">
          {analyzeUrl.trim()
            ? `Context: ${analyzeUrl.trim().replace(/^https?:\/\//, "").slice(0, 30)}`
            : "No URL context — set one below"}
        </span>
      </div>

      {/* Analyze bar */}
      <div className="border-b border-border px-6 py-2.5 flex items-center gap-3 bg-card/50">
        <label className="text-xs text-muted uppercase tracking-wide shrink-0">Analyze URL</label>
        <input
          type="url"
          value={analyzeUrl}
          onChange={(e) => setAnalyzeUrl(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") handleAnalyze(); }}
          placeholder="https://example.com"
          className="flex-1 max-w-md bg-black/40 border border-border rounded-lg px-3 py-1.5 text-sm text-white placeholder-muted focus:outline-none focus:border-indigo-500 transition-colors"
        />
        <button
          onClick={handleAnalyze}
          disabled={analyzing || !analyzeUrl.trim()}
          className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium px-4 py-1.5 rounded-lg transition-colors flex items-center gap-2"
        >
          {analyzing ? (
            <>
              <span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              Dispatching...
            </>
          ) : (
            "Analyze"
          )}
        </button>
        <span className="text-[10px] text-muted">
          Quick URL scan — dispatches all 4 agents
        </span>
      </div>

      {/* Synthesis panel */}
      {showSynthesis && showSynthesis.result && (
        <div className="border-b border-border bg-emerald-950/30 px-6 py-4 max-h-[50vh] overflow-y-auto">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <span className="text-emerald-400 font-semibold text-sm">Orchestrator Synthesis</span>
              <span className="text-[10px] text-muted">
                {showSynthesis.description}
              </span>
            </div>
            <button
              onClick={() => setShowSynthesis(null)}
              className="text-muted hover:text-white text-xs transition-colors"
            >
              ✕ Close
            </button>
          </div>
          <pre className="text-sm text-gray-200 whitespace-pre-wrap break-words font-mono leading-relaxed">
            {showSynthesis.result}
          </pre>
        </div>
      )}

      {/* Main content */}
      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* Left — agents + log */}
        <main className="flex-1 flex flex-col gap-5 px-6 py-5 overflow-y-auto min-w-0">
          <AgentBoard
            agents={agents}
            onSelectAgent={setSelectedAgent}
            onReplace={setReplaceTarget}
            onRestore={handleRestore}
          />
          <LogStream />
        </main>

        {/* Right sidebar — tasks */}
        <aside className="w-80 shrink-0 border-l border-border px-4 py-5 flex flex-col overflow-hidden">
          <TaskPanel
            tasks={tasks}
            agents={agents}
            onSubmit={submit}
            onRemove={remove}
            onChatOrchestrator={() =>
              setSelectedAgent({
                id: "orchestrator",
                role: "strategic synthesizer",
                goal: "Synthesize findings across all agents",
                model: "claude-haiku-4-5",
                color: "#10b981",
                tools: [],
                status: "idle",
                current_task: null,
                last_output: null,
              })
            }
          />
        </aside>
      </div>

      {/* Chat drawer overlay */}
      {selectedAgent && (
        <ChatDrawer
          key={selectedAgent.id}
          agent={selectedAgent}
          onClose={() => setSelectedAgent(null)}
        />
      )}

      {replaceTarget && (
        <ReplaceAgentModal
          agentId={replaceTarget.id}
          agentName={replaceTarget.role || replaceTarget.id}
          onClose={() => setReplaceTarget(null)}
          onReplaced={() => {
            setReplaceTarget(null);
            refreshAgents();
          }}
        />
      )}
    </div>
  );
}
