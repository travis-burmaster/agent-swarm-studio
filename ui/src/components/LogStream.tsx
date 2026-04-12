import React, { useState, useEffect, useRef } from 'react'
import { WS_URL } from '../lib/api'

interface LogEntry {
  id: number
  message: string
  ts: string
}

function formatEvent(ev: Record<string, unknown>): string {
  switch (ev.type) {
    case 'task_phase':
      return `[${ev.agent_id}] · ${ev.phase}${ev.detail ? ` | ${ev.detail}` : ''}`
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
    case 'tool_called':
      return `[${ev.agent_id}] 🛠 ${ev.tool_name}(${String(ev.tool_input_preview || '').slice(0, 80)})`
    case 'tool_result':
      return `[${ev.agent_id}] ↳ ${ev.tool_name} → ${String(ev.result_preview || '').slice(0, 90)}`
    case 'workflow_started':
      return `[workflow:${ev.workflow_id}] ▶ started for ${ev.company_url} | agents: ${Array.isArray(ev.agents) ? ev.agents.join(', ') : ev.agents}`
    case 'workflow_progress':
      return `[workflow:${ev.workflow_id}] … progress ${ev.completed}/${ev.total} complete, ${ev.failed} failed`
    case 'workflow_timeout':
      return `[workflow:${ev.workflow_id}] ⏱ timeout | waiting on: ${Array.isArray(ev.timed_out_agents) ? ev.timed_out_agents.join(', ') : ev.timed_out_agents}`
    case 'workflow_synthesis_started':
      return `[workflow:${ev.workflow_id}] 🧠 synthesis started | completed=${ev.completed}, failed=${ev.failed}${Array.isArray(ev.timed_out_agents) && ev.timed_out_agents.length ? `, timed out: ${ev.timed_out_agents.join(', ')}` : ''}`
    case 'workflow_completed':
      return `[workflow:${ev.workflow_id}] ✓ ${ev.status} for ${ev.company_url}${Array.isArray(ev.failed_agents) && ev.failed_agents.length ? ` | failed: ${ev.failed_agents.join(', ')}` : ''}${Array.isArray(ev.timed_out_agents) && ev.timed_out_agents.length ? ` | timed out: ${ev.timed_out_agents.join(', ')}` : ''}`
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
