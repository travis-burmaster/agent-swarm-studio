import React from "react";
import { Agent } from "../lib/api";
import AgentCard from "./AgentCard";

interface AgentBoardProps {
  agents: Agent[];
  onSelectAgent: (agent: Agent) => void;
}

export default function AgentBoard({ agents, onSelectAgent }: AgentBoardProps) {
  return (
    <section>
      <h2 className="text-xs font-semibold uppercase tracking-widest text-muted mb-3">
        Agents
      </h2>
      {agents.length === 0 ? (
        <div className="text-muted text-sm py-8 text-center border border-border rounded-xl">
          No agents configured. Check your <code className="text-gray-400">agents.yaml</code>.
        </div>
      ) : (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {agents.map((agent) => (
            <AgentCard
              key={agent.id}
              agent={agent}
              onClick={() => onSelectAgent(agent)}
            />
          ))}
        </div>
      )}
    </section>
  );
}
