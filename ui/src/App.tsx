import React, { useState } from 'react'
import { AgentBoard } from './components/AgentBoard'
import { TaskPanel } from './components/TaskPanel'
import { ChatDrawer } from './components/ChatDrawer'
import { LogStream } from './components/LogStream'
import { useAgents, Agent } from './hooks/useAgents'
import { useTasks } from './hooks/useTasks'

export default function App() {
  const { agents } = useAgents()
  const { tasks, submit, remove } = useTasks()
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null)

  const pendingCount = tasks.filter(t => t.status === 'pending').length

  return (
    <div className="min-h-screen bg-surface text-white flex flex-col">
      {/* Header */}
      <header className="border-b border-border px-6 py-3 flex items-center gap-3 shrink-0">
        <div className="w-2 h-2 rounded-full bg-indigo-500" />
        <span className="font-semibold tracking-tight">Agent Swarm Studio</span>
        <span className="text-xs text-muted ml-2">
          {agents.length} agent{agents.length !== 1 ? 's' : ''}
          {pendingCount > 0 && ` · ${pendingCount} pending`}
        </span>
        <div className="ml-auto flex items-center gap-2 text-xs text-muted">
          <div className="w-1.5 h-1.5 rounded-full bg-green-500" />
          connected
        </div>
      </header>

      {/* Main layout */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left: agents + log stream */}
        <div className="flex-1 flex flex-col p-6 gap-4 overflow-y-auto min-w-0">
          <AgentBoard agents={agents} onSelectAgent={setSelectedAgent} />
          <LogStream />
        </div>

        {/* Right: task panel */}
        <div className="w-80 border-l border-border p-4 flex flex-col overflow-hidden shrink-0">
          <TaskPanel tasks={tasks} onSubmit={submit} onDelete={remove} />
        </div>
      </div>

      {/* Chat drawer overlay */}
      <ChatDrawer agent={selectedAgent} onClose={() => setSelectedAgent(null)} />
    </div>
  )
}
