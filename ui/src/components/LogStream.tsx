import React, { useState, useEffect, useRef } from 'react'
import { WS_URL } from '../lib/api'

interface LogEntry {
  id: number
  message: string
  ts: string
}

function formatEvent(ev: Record<string, unknown>): string {
  switch (ev.type) {
    case 'agent_status':
      return `[${ev.agent_id}] status → ${ev.status}${ev.current_task ? ` | ${ev.current_task}` : ''}`
    case 'task_created':
      return `[task:${ev.task_id}] created → ${ev.assigned_to}: ${String(ev.description).slice(0, 80)}`
    case 'task_started':
      return `[${ev.agent_id}] ▶ started task:${ev.task_id}`
    case 'task_completed':
      return `[${ev.agent_id}] ✓ completed task:${ev.task_id}`
    case 'task_error':
      return `[${ev.agent_id}] ✗ error: ${ev.error}`
    case 'chat_message':
      return `[chat:${ev.agent_id}] ${String(ev.preview || ev.message).slice(0, 60)}`
    default:
      return JSON.stringify(ev).slice(0, 120)
  }
}

export function LogStream() {
  const [logs, setLogs] = useState<LogEntry[]>([])
  const counter = useRef(0)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const ws = new WebSocket(`${WS_URL}/ws/events`)
    ws.onmessage = (e) => {
      try {
        const ev = JSON.parse(e.data)
        const entry: LogEntry = {
          id: ++counter.current,
          message: formatEvent(ev),
          ts: new Date().toLocaleTimeString(),
        }
        setLogs(prev => [...prev.slice(-199), entry])
      } catch {}
    }
    return () => ws.close()
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  return (
    <div className="bg-black/60 border border-border rounded-xl p-3 h-40 overflow-y-auto font-mono">
      <div className="text-xs text-muted mb-2 uppercase tracking-widest">Live Events</div>
      {logs.length === 0 && (
        <div className="text-muted text-xs">Waiting for events...</div>
      )}
      {logs.map(l => (
        <div key={l.id} className="text-xs text-gray-300 leading-relaxed">
          <span className="text-gray-600 mr-2">{l.ts}</span>
          {l.message}
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  )
}
