import React, { useState, useRef, useEffect, useCallback } from 'react'
import { useChat } from '../hooks/useChat'

interface Agent {
  id: string
  role: string
  color: string
}

interface Props {
  agent: Agent | null
  onClose: () => void
}

const MIN_WIDTH = 320
const MAX_WIDTH = 800
const DEFAULT_WIDTH = 384

export function ChatDrawer({ agent, onClose }: Props) {
  const [input, setInput] = useState('')
  const { messages, send, loading } = useChat(agent?.id ?? '')
  const bottomRef = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(DEFAULT_WIDTH)
  const dragging = useRef(false)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    dragging.current = true

    const onMouseMove = (e: MouseEvent) => {
      if (!dragging.current) return
      const newWidth = window.innerWidth - e.clientX
      setWidth(Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, newWidth)))
    }

    const onMouseUp = () => {
      dragging.current = false
      document.removeEventListener('mousemove', onMouseMove)
      document.removeEventListener('mouseup', onMouseUp)
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }

    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
    document.addEventListener('mousemove', onMouseMove)
    document.addEventListener('mouseup', onMouseUp)
  }, [])

  if (!agent) return null

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || loading) return
    const text = input.trim()
    setInput('')
    await send(text)
  }

  return (
    <div className="fixed inset-y-0 right-0 bg-card border-l border-border flex flex-col z-50 shadow-2xl" style={{ width }}>
      {/* Resize handle */}
      <div
        onMouseDown={onMouseDown}
        className="absolute inset-y-0 left-0 w-1.5 cursor-col-resize hover:bg-indigo-500/40 transition-colors z-10"
      />
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: agent.color }} />
          <span className="font-semibold text-sm">{agent.id}</span>
          <span className="text-xs text-muted">{agent.role}</span>
        </div>
        <button onClick={onClose} className="text-muted hover:text-white transition-colors text-lg leading-none">
          ✕
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.length === 0 && (
          <p className="text-muted text-sm text-center mt-8">
            Chat directly with <span className="text-white font-medium">{agent.id}</span>
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className={`max-w-[80%] rounded-xl px-3 py-2 text-sm whitespace-pre-wrap ${
                m.role === 'user'
                  ? 'bg-indigo-600 text-white'
                  : 'bg-black/50 border border-border text-gray-200'
              }`}
            >
              {m.content}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-black/50 border border-border rounded-xl px-3 py-2 text-sm text-muted">
              Thinking...
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSend} className="p-3 border-t border-border flex gap-2">
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder={`Message ${agent.id}...`}
          className="flex-1 bg-black/40 border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-gray-500 text-white placeholder-muted"
          disabled={loading}
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="px-3 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 rounded-lg text-sm transition-colors"
        >
          ↑
        </button>
      </form>
    </div>
  )
}
