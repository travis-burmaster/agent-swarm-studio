import React from "react";
import { Agent } from "../lib/api";

interface AgentCardProps {
  agent: Agent;
  onClick: () => void;
}

function StatusDot({ status }: { status: Agent["status"] }) {
  const colors: Record<Agent["status"], string> = {
    idle: "bg-green-500",
    working: "bg-yellow-400 animate-pulse",
    error: "bg-red-500",
    offline: "bg-gray-600",
  };
  return (
    <span
      className={`inline-block w-2.5 h-2.5 rounded-full ${colors[status] ?? "bg-gray-600"}`}
      title={status}
    />
  );
}

export default function AgentCard({ agent, onClick }: AgentCardProps) {
  return (
    <button
      onClick={onClick}
      className="text-left w-full bg-card border border-border rounded-xl p-4 hover:border-gray-600 hover:bg-[#181818] transition-all duration-150 flex flex-col gap-2"
      style={{ borderLeftColor: agent.color, borderLeftWidth: "3px" }}
    >
      {/* Header */}
      <div className="flex items-center justify-between gap-2">
        <span className="font-mono text-xs text-muted uppercase tracking-widest">
          {agent.id}
        </span>
        <div className="flex items-center gap-2">
          <span
            onClick={(e) => { e.stopPropagation(); onClick(); }}
            className="text-[10px] text-indigo-400 hover:text-indigo-300 cursor-pointer transition-colors border border-indigo-500/50 hover:border-indigo-400 rounded px-1.5 py-0.5"
          >
            Chat
          </span>
          <StatusDot status={agent.status} />
        </div>
      </div>

      {/* Role */}
      <div className="font-semibold text-white text-sm leading-tight">
        {agent.role}
      </div>

      {/* Current task */}
      {agent.current_task && (
        <div className="text-xs text-yellow-400 truncate" title={agent.current_task}>
          ⚙ {agent.current_task}
        </div>
      )}

      {/* Last output */}
      {agent.last_output && !agent.current_task && (
        <div className="text-xs text-muted line-clamp-2" title={agent.last_output}>
          {agent.last_output}
        </div>
      )}

      {/* Status badge */}
      <div className="mt-auto pt-1">
        <span
          className={`text-[10px] font-medium px-1.5 py-0.5 rounded uppercase tracking-wide ${
            agent.status === "working"
              ? "bg-yellow-900/50 text-yellow-300"
              : agent.status === "error"
              ? "bg-red-900/50 text-red-300"
              : agent.status === "idle"
              ? "bg-green-900/50 text-green-300"
              : "bg-gray-800 text-gray-500"
          }`}
        >
          {agent.status}
        </span>
      </div>
    </button>
  );
}
