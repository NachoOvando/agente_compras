'use client';

import { ChatCircle, CircleNotch, PaperPlaneTilt } from '@phosphor-icons/react/dist/ssr';
import { useEffect, useRef, useState } from 'react';
import MessageBubble from '@/components/MessageBubble/MessageBubble';
import { appConfig } from '@/lib/app-config';
import type { ChatMessage } from '@/lib/types';

interface ChatWindowProps {
  messages: ChatMessage[];
  loading: boolean;
  onSend: (question: string) => void;
}

export default function ChatWindow({
  messages,
  loading,
  onSend,
}: ChatWindowProps) {
  const [input, setInput] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const question = input.trim();
    if (!question || loading) return;
    setInput('');
    onSend(question);
  };

  return (
    <div className="flex h-[32rem] flex-col rounded-xl border border-border bg-card shadow-sm">
      <div
        className="flex-1 space-y-3 overflow-y-auto p-4"
        role="log"
        aria-live="polite"
        aria-label="Historial de la conversación"
      >
        {messages.length === 0 && (
          <div className="flex flex-col items-center gap-2 pt-16 text-center text-sm text-muted-foreground">
            <ChatCircle size={28} weight="regular" aria-hidden="true" />
            <p>
              Hacé una pregunta sobre los insumos críticos del{' '}
              {appConfig.producto}, o elegí una de las preguntas de ejemplo.
            </p>
          </div>
        )}
        {messages.map((msg, i) => (
          <MessageBubble key={i} message={msg} />
        ))}
        {loading && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <CircleNotch size={16} weight="bold" className="animate-spin" aria-hidden="true" />
            <span>Consultando el cerco de información…</span>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
      <form
        onSubmit={handleSubmit}
        className="flex gap-2 border-t border-border p-3"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ej: ¿qué insumo tengo que comprar primero?"
          className="flex-1 rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground outline-none transition-colors duration-200 focus:border-accent"
          aria-label="Pregunta al asistente"
        />
        <button
          type="submit"
          disabled={loading || input.trim().length === 0}
          className="flex cursor-pointer items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-on-primary transition-colors duration-200 hover:bg-secondary disabled:cursor-not-allowed disabled:opacity-50"
        >
          <PaperPlaneTilt size={16} weight="regular" aria-hidden="true" />
          Enviar
        </button>
      </form>
    </div>
  );
}
