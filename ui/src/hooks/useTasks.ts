import { useCallback, useEffect, useState } from "react";
import { clearAllTasks, createTask, deleteTask, getTasks, Task } from "../lib/api";

export function useTasks() {
  const [tasks, setTasks] = useState<Task[]>([]);

  const refresh = useCallback(async () => {
    try {
      const data = await getTasks();
      setTasks(data);
    } catch (err) {
      console.error("Failed to fetch tasks:", err);
    }
  }, []);

  // Initial fetch + poll every 5s for async updates (synthesis, agent results)
  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 5000);
    return () => clearInterval(interval);
  }, [refresh]);

  const submit = useCallback(
    async (description: string, assignTo: string = "orchestrator") => {
      await createTask(description, assignTo);
      await refresh();
    },
    [refresh]
  );

  const remove = useCallback(
    async (id: string) => {
      await deleteTask(id);
      await refresh();
    },
    [refresh]
  );

  const clear = useCallback(async () => {
    await clearAllTasks();
    await refresh();
  }, [refresh]);

  return { tasks, submit, remove, clear, refresh };
}
