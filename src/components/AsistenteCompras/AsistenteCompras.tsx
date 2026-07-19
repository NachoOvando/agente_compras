'use client';

import { useCallback, useEffect, useState } from 'react';
import ChatWindow from '@/components/ChatWindow/ChatWindow';
import SampleQuestions from '@/components/SampleQuestions/SampleQuestions';
import StockPanel from '@/components/StockPanel/StockPanel';
import { askQuestion, fetchStock } from '@/lib/api-client';
import { appConfig } from '@/lib/app-config';
import type { ChatMessage, HistoryTurn, Stock } from '@/lib/types';

// Mismo tope que el server (engine.config.MAX_HISTORY_TURNS * 2), para no
// mandar un historial que el backend igual va a rechazar con 422.
const MAX_HISTORY_MESSAGES = 20;

export default function AsistenteCompras() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [stock, setStock] = useState<Stock | null>(null);
  const [stockError, setStockError] = useState<string | null>(null);
  const [overrides, setOverrides] = useState<Record<string, number>>({});

  useEffect(() => {
    fetchStock()
      .then(setStock)
      .catch((err: Error) => setStockError(err.message));
  }, []);

  const handleSend = useCallback(
    async (question: string) => {
      if (loading) return;
      // Historial ANTES de agregar la pregunta nueva (que va aparte, como
      // `question`) — solo turnos válidos, sin errores, con tope al igual
      // que el server.
      const history: HistoryTurn[] = messages
        .filter((m) => !m.isError)
        .slice(-MAX_HISTORY_MESSAGES)
        .map((m) => ({ role: m.role, content: m.content }));

      setMessages((prev) => [...prev, { role: 'user', content: question }]);
      setLoading(true);
      try {
        const hasOverrides = Object.keys(overrides).length > 0;
        const result = await askQuestion(
          question,
          hasOverrides ? overrides : undefined,
          history.length > 0 ? history : undefined,
        );
        setMessages((prev) => [
          ...prev,
          { role: 'assistant', content: result.answer },
        ]);
      } catch (err) {
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content:
              err instanceof Error ? err.message : 'Error inesperado.',
            isError: true,
          },
        ]);
      } finally {
        setLoading(false);
      }
    },
    [loading, overrides, messages],
  );

  return (
    <div className="flex flex-col gap-6 lg:flex-row">
      <section className="flex min-w-0 flex-1 flex-col gap-4">
        <SampleQuestions
          questions={appConfig.preguntasDemo}
          onSelect={handleSend}
          disabled={loading}
        />
        <ChatWindow messages={messages} onSend={handleSend} loading={loading} />
      </section>
      <aside className="w-full shrink-0 lg:w-80">
        <StockPanel
          stock={stock}
          error={stockError}
          overrides={overrides}
          onChangeOverride={(codigo, valor) =>
            setOverrides((prev) => {
              if (valor === null) {
                const { [codigo]: _omitido, ...resto } = prev;
                return resto;
              }
              return { ...prev, [codigo]: valor };
            })
          }
          onReset={() => setOverrides({})}
        />
      </aside>
    </div>
  );
}
