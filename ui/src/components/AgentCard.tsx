import React, { useEffect, useRef, useState } from "react";
import { Agent, getReplacementInfo, ReplacementInfo } from "../lib/api";

interface AgentCardProps {
  agent: Agent;
  onClick: () => void;
  onReplace: (agent: Agent) => void;
  onRestore: (agentId: string) => void;
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

export default function AgentCard({ agent, onClick, onReplace, onRestore }: AgentCardProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [replacementInfo, setReplacementInfo] = useState<ReplacementInfo | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  // Fetch replacement info on mount
  useEffect(() => {
    getReplacementInfo(agent.id)
      .then(setReplacementInfo)
      .catch(() => {});
  }, [agent.id]);

  // Close menu on outside click
  useEffect(() => {
    if (!menuOpen) return;
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [menuOpen]);

  const isReplaced = replacementInfo?.is_replaced ?? false;

  return (
    <div className="relative">
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
            {/* Dropdown trigger */}
            <span
              onClick={(e) => {
                e.stopPropagation();
                setMenuOpen((prev) => !prev);
              }}
              className="text-[10px] text-gray-400 hover:text-white cursor-pointer transition-colors border border-border hover:border-gray-500 rounded px-1.5 py-0.5"
              title="Agent options"
            >
              ...
            </span>
            <StatusDot status={agent.status} />
          </div>
        </div>

        {/* Role */}
        <div className="font-semibold text-white text-sm leading-tight">
          {agent.role}
        </div>

        {/* Registry badge */}
        {isReplaced && replacementInfo?.replacement_name && (
          <div className="flex items-center gap-1">
            <span className="text-[9px] bg-purple-900/50 text-purple-300 border border-purple-700/50 rounded px-1.5 py-0.5 font-mono">
              registry: {replacementInfo.replacement_name}
            </span>
          </div>
        )}

        {/* Current task */}
        {agent.current_task && (
          <div className="text-xs text-yellow-400 truncate" title={agent.current_task}>
            {agent.current_task}
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

      {/* Dropdown menu */}
      {menuOpen && (
        <div
          ref={menuRef}
          className="absolute right-2 top-10 z-20 bg-[#1a1a1a] border border-border rounded-lg shadow-xl py-1 min-w-[180px]"
        >
          <button
            onClick={() => {
              setMenuOpen(false);
              onReplace(agent);
            }}
            className="w-full text-left px-3 py-2 text-xs text-gray-300 hover:bg-white/5 hover:text-white transition-colors"
          >
            Replace with Registry Agent
          </button>
          {isReplaced && (
            <button
              onClick={() => {
                setMenuOpen(false);
                onRestore(agent.id);
              }}
              className="w-full text-left px-3 py-2 text-xs text-amber-400 hover:bg-white/5 hover:text-amber-300 transition-colors"
            >
              Restore Original
            </button>
          )}
        </div>
      )}
    </div>
  );
}
