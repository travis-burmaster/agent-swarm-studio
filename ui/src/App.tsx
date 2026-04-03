import React, { useState } from "react";
import { Agent } from "./lib/api";
import { useAgents } from "./hooks/useAgents";
import { useTasks } from "./hooks/useTasks";
import AgentBoard from "./components/AgentBoard";
import TaskPanel from "./components/TaskPanel";
import ChatDrawer from "./components/ChatDrawer";
import LogStream from "./components/LogStream";

export default function App() {
  const { agents, refresh: refreshAgents } = useAgents();
  const { tasks, submit, remove, refresh: refreshTasks } = useTasks();
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);

  const pendingCount = tasks.filter((t) => t.status === "pending" || t.status === "in_progress").length;
  const activeAgents = agents.filter((a) => a.status !== "offline").length;

  return (
    <div className="min-h-screen bg-surface flex flex-col">
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
          <button
            onClick={() => { refreshAgents(); refreshTasks(); }}
            className="text-muted hover:text-white text-xs px-2 py-1 border border-border rounded-md transition-colors"
            title="Refresh"
          >
            ↻ Refresh
          </button>
        </div>
      </header>

      {/* Main content */}
      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* Left — agents + log */}
        <main className="flex-1 flex flex-col gap-5 px-6 py-5 overflow-y-auto min-w-0">
          <AgentBoard agents={agents} onSelectAgent={setSelectedAgent} />
          <LogStream />
        </main>

        {/* Right sidebar — tasks */}
        <aside className="w-80 shrink-0 border-l border-border px-4 py-5 flex flex-col overflow-hidden">
          <TaskPanel
            tasks={tasks}
            agents={agents}
            onSubmit={submit}
            onRemove={remove}
          />
        </aside>
      </div>

      {/* Chat drawer overlay */}
      {selectedAgent && (
        <ChatDrawer
          agent={selectedAgent}
          onClose={() => setSelectedAgent(null)}
        />
      )}
    </div>
  );
}
