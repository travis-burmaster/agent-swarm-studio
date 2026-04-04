import axios from "axios";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
export const WS_URL = import.meta.env.VITE_WS_URL ?? "ws://localhost:8000";

const api = axios.create({
  baseURL: API_URL,
  headers: { "Content-Type": "application/json" },
});

// ── Agent types ───────────────────────────────────────────────────────────────

export interface Agent {
  id: string;
  role: string;
  goal: string;
  model: string;
  color: string;
  tools: string[];
  status: "idle" | "working" | "error" | "offline";
  current_task: string | null;
  last_output: string | null;
}

// ── Task types ────────────────────────────────────────────────────────────────

export interface Task {
  id: string;
  description: string;
  assign_to: string;
  status: "pending" | "in_progress" | "completed" | "failed";
  result: string | null;
  created_at: string;
  updated_at: string;
}

// ── API functions ─────────────────────────────────────────────────────────────

export const getAgents = (): Promise<Agent[]> =>
  api.get<Agent[]>("/agents").then((r) => r.data);

export const getTasks = (): Promise<Task[]> =>
  api.get<Task[]>("/tasks").then((r) => r.data);

export const createTask = (
  description: string,
  assign_to: string = "orchestrator"
): Promise<Task> =>
  api.post<Task>("/tasks", { description, assign_to }).then((r) => r.data);

export const deleteTask = (id: string): Promise<void> =>
  api.delete(`/tasks/${id}`).then(() => undefined);

export const clearHistory = (): Promise<{ cleared: boolean }> =>
  api.delete("/tasks").then((r) => r.data);

export const sendChat = (
  agentId: string,
  message: string
): Promise<{ agent_id: string; reply: string }> =>
  api.post(`/chat/${agentId}`, { message }).then((r) => r.data);

export default api;
