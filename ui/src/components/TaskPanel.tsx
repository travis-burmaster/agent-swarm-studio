import React, { useState, useRef, useLayoutEffect } from "react";
import { Agent, Task } from "../lib/api";

const expandedSet = new Set<string>();

interface TaskPanelProps {
  tasks: Task[];
  agents: Agent[];
  onSubmit: (description: string, assignTo: string) => Promise<void>;
  onRemove: (id: string) => Promise<void>;
}

function statusBadge(status: Task["status"]) {
  const map: Record<Task["status"], string> = {
    pending: "bg-yellow-900/60 text-yellow-300",
    in_progress: "bg-blue-900/60 text-blue-300",
    completed: "bg-green-900/60 text-green-300",
    failed: "bg-red-900/60 text-red-300",
  };
  return map[status] ?? "bg-gray-800 text-gray-400";
}

export default function TaskPanel({ tasks, agents, onSubmit, onRemove }: TaskPanelProps) {
  const [description, setDescription] = useState("");
  const [assignTo, setAssignTo] = useState("orchestrator");
  const [submitting, setSubmitting] = useState(false);
  const [expanded, setExpanded] = useState<Set<string>>(() => expandedSet);
  const listRef = useRef<HTMLDivElement>(null);
  const scrollTopRef = useRef(0);

  // Save scroll position before DOM updates
  useLayoutEffect(() => {
    const el = listRef.current;
    if (el) {
      scrollTopRef.current = el.scrollTop;
    }
  });

  // Restore scroll position after tasks change
  useLayoutEffect(() => {
    const el = listRef.current;
    if (el) {
      el.scrollTop = scrollTopRef.current;
    }
  }, [tasks]);

  const toggleExpand = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!description.trim()) return;
    setSubmitting(true);
    try {
      await onSubmit(description.trim(), assignTo);
      setDescription("");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex flex-col gap-4 h-full">
      <h2 className="text-xs font-semibold uppercase tracking-widest text-muted">
        Tasks
      </h2>

      {/* Task creation form */}
      <form onSubmit={handleSubmit} className="flex flex-col gap-2">
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Describe a task for the swarm…"
          rows={3}
          className="w-full bg-card border border-border rounded-lg px-3 py-2 text-sm text-white placeholder-muted resize-none focus:outline-none focus:border-indigo-500 transition-colors"
        />
        <div className="flex gap-2">
          <select
            value={assignTo}
            onChange={(e) => setAssignTo(e.target.value)}
            className="flex-1 bg-card border border-border rounded-lg px-2 py-1.5 text-sm text-white focus:outline-none focus:border-indigo-500"
          >
            {agents.length > 0
              ? agents.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.id}
                  </option>
                ))
              : <option value="orchestrator">orchestrator</option>}
          </select>
          <button
            type="submit"
            disabled={submitting || !description.trim()}
            className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium px-4 py-1.5 rounded-lg transition-colors"
          >
            {submitting ? "Sending…" : "Submit"}
          </button>
        </div>
      </form>

      {/* Task list */}
      <div ref={listRef} className="flex-1 overflow-y-auto space-y-2 min-h-0">
        {tasks.length === 0 && (
          <div className="text-muted text-xs text-center py-6">No tasks yet.</div>
        )}
        {tasks.map((task) => (
          <div
            key={task.id}
            className="bg-card border border-border rounded-lg px-3 py-2 flex flex-col gap-1"
          >
            <div className="flex items-start justify-between gap-2">
              <span
                className={`text-[10px] font-semibold px-1.5 py-0.5 rounded uppercase tracking-wide shrink-0 ${statusBadge(task.status)}`}
              >
                {task.status.replace("_", " ")}
              </span>
              <button
                onClick={() => onRemove(task.id)}
                className="text-muted hover:text-red-400 text-xs shrink-0 transition-colors"
                title="Delete task"
              >
                ✕
              </button>
            </div>
            <p className="text-sm text-white leading-snug line-clamp-2">
              {task.description}
            </p>
            <div className="flex items-center justify-between">
              <p className="text-[11px] text-muted">→ {task.assign_to}</p>
              {task.result && (
                <button
                  onClick={() => toggleExpand(task.id)}
                  className="text-[10px] text-indigo-400 hover:text-indigo-300 transition-colors"
                >
                  {expanded.has(task.id) ? "▾ Hide result" : "▸ View result"}
                </button>
              )}
            </div>
            {task.result && expanded.has(task.id) && (
              <div className="mt-1 bg-black/40 border border-border rounded-md px-3 py-2 max-h-64 overflow-y-auto">
                <pre className="text-xs text-gray-300 whitespace-pre-wrap break-words font-mono leading-relaxed">
                  {task.result}
                </pre>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
