import { useCallback, useState } from "react";
import { sendChat } from "../lib/api";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export function useChat(agentId: string) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);

  const send = useCallback(
    async (text: string) => {
      if (!text.trim()) return;

      const userMessage: ChatMessage = { role: "user", content: text };
      setMessages((prev) => [...prev, userMessage]);
      setLoading(true);

      try {
        const response = await sendChat(agentId, text);
        const assistantMessage: ChatMessage = {
          role: "assistant",
          content: response.reply,
        };
        setMessages((prev) => [...prev, assistantMessage]);
      } catch (err) {
        console.error("Chat error:", err);
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: "⚠️ Error: failed to get a response." },
        ]);
      } finally {
        setLoading(false);
      }
    },
    [agentId]
  );

  return { messages, send, loading };
}
