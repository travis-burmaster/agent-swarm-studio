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

// ── Replacement types ────────────────────────────────────────────────────────

export interface ReplaceResult {
  agent_id: string;
  new_name: string;
  new_role: string;
  registry_url: string;
  backup_exists: boolean;
  status: string;
}

export interface RestoreResult {
  agent_id: string;
  restored_name: string;
  restored_role: string;
  status: string;
}

export interface ReplacementInfo {
  agent_id: string;
  is_replaced: boolean;
  registry_url: string | null;
  replacement_name: string | null;
  replaced_at: string | null;
  backup_exists: boolean;
  original_name: string | null;
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

export const sendChat = (
  agentId: string,
  message: string
): Promise<{ agent_id: string; reply: string }> =>
  api.post(`/chat/${agentId}`, { message }).then((r) => r.data);

// ── Workflow functions ────────────────────────────────────────────────────────

export interface Workflow {
  workflow_id: string;
  company_url: string;
  status: string;
  tasks: Record<string, string>;
}

export const startAnalysis = (companyUrl: string): Promise<Workflow> =>
  api.post<Workflow>("/workflow/analyze", { company_url: companyUrl }).then((r) => r.data);

export const askAllAgents = (
  question: string,
  companyUrl?: string
): Promise<Workflow> =>
  api
    .post<Workflow>("/workflow/question", {
      question,
      company_url: companyUrl || undefined,
    })
    .then((r) => r.data);

export const getConfig = (): Promise<{ target_company_url: string }> =>
  api.get<{ target_company_url: string }>("/config").then((r) => r.data);

// ── Agent replacement functions ──────────────────────────────────────────────

export const replaceAgent = (
  agentId: string,
  registryUrl: string
): Promise<ReplaceResult> =>
  api
    .post<ReplaceResult>(`/agents/${agentId}/replace`, {
      registry_url: registryUrl,
    })
    .then((r) => r.data);

export const restoreAgent = (agentId: string): Promise<RestoreResult> =>
  api.post<RestoreResult>(`/agents/${agentId}/restore`).then((r) => r.data);

export const getReplacementInfo = (
  agentId: string
): Promise<ReplacementInfo> =>
  api
    .get<ReplacementInfo>(`/agents/${agentId}/replacement-info`)
    .then((r) => r.data);

export default api;
