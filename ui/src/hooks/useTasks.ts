import { useCallback, useEffect, useState } from "react";
import { createTask, deleteTask, getTasks, Task } from "../lib/api";

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

  // Initial fetch
  useEffect(() => {
    refresh();
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

  return { tasks, submit, remove, refresh };
}
