import { useCallback, useEffect, useRef, useState } from "react";
import { Agent, getAgents, WS_URL } from "../lib/api";

export function useAgents() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await getAgents();
      setAgents(data);
    } catch (err) {
      console.error("Failed to fetch agents:", err);
    }
  }, []);

  // Initial fetch + poll every 5s as fallback when WebSocket is disconnected
  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 5000);
    return () => clearInterval(interval);
  }, [refresh]);

  // WebSocket for live agent_status events
  useEffect(() => {
    const connect = () => {
      const ws = new WebSocket(`${WS_URL}/ws/events`);
      wsRef.current = ws;

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data as string);
          if (data.type === "agent_status") {
            const { agent_id, status, current_task, last_output } = data;
            setAgents((prev) =>
              prev.map((a) =>
                a.id === agent_id
                  ? { ...a, status, current_task: current_task ?? null, last_output: last_output ?? null }
                  : a
              )
            );
          }
        } catch {
          // ignore malformed messages
        }
      };

      ws.onclose = () => {
        // Reconnect after 3 seconds
        setTimeout(connect, 3000);
      };

      ws.onerror = () => {
        ws.close();
      };
    };

    connect();

    return () => {
      wsRef.current?.close();
    };
  }, []);

  return { agents, refresh };
}
