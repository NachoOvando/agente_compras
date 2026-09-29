import { WarningCircle } from '@phosphor-icons/react/dist/ssr';
import { isValidElement, type ReactNode } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { ChatMessage } from '@/lib/types';

interface MessageBubbleProps {
  message: ChatMessage;
}

function nodeToText(node: ReactNode): string {
  if (typeof node === 'string' || typeof node === 'number') return String(node);
  if (Array.isArray(node)) return node.map(nodeToText).join('');
  if (isValidElement(node)) return nodeToText((node.props as { children?: ReactNode }).children);
  return '';
}

// Celdas de veredicto ("Sí", "No", "Alcanza", "Falta") → badge de color.
function estadoDeCelda(texto: string): 'ok' | 'mal' | null {
  const t = texto.toLowerCase().replace(/[*_.]/g, '');
  if (/^(sí|si|alcanza|suficiente|ok)$/.test(t)) return 'ok';
  if (/^(no|no alcanza|falta|insuficiente)$/.test(t)) return 'mal';
  return null;
}

// Mapeo de elementos markdown a los tokens de color/espaciado del proyecto,
// para no depender del plugin de Tailwind typography.
const markdownComponents = {
  p: ({ children }: { children?: ReactNode }) => (
    <p className="mb-2 last:mb-0">{children}</p>
  ),
  ul: ({ children }: { children?: ReactNode }) => (
    <ul className="mb-2 ml-4 list-disc space-y-0.5 last:mb-0">{children}</ul>
  ),
  ol: ({ children }: { children?: ReactNode }) => (
    <ol className="mb-2 ml-4 list-decimal space-y-0.5 last:mb-0">{children}</ol>
  ),
  strong: ({ children }: { children?: ReactNode }) => (
    <strong className="font-semibold">{children}</strong>
  ),
  h1: ({ children }: { children?: ReactNode }) => (
    <h3 className="mb-2 text-base font-semibold">{children}</h3>
  ),
  h2: ({ children }: { children?: ReactNode }) => (
    <h3 className="mb-2 text-base font-semibold">{children}</h3>
  ),
  h3: ({ children }: { children?: ReactNode }) => (
    <h4 className="mb-1.5 text-sm font-semibold">{children}</h4>
  ),
  hr: () => <hr className="my-3 border-border" />,
  blockquote: ({ children }: { children?: ReactNode }) => (
    <blockquote className="mb-2 border-l-2 border-accent pl-3 text-muted-foreground last:mb-0">
      {children}
    </blockquote>
  ),
  code: ({ children }: { children?: ReactNode }) => (
    <code className="rounded bg-border/60 px-1 py-0.5 font-mono text-[0.85em]">{children}</code>
  ),
  table: ({ children }: { children?: ReactNode }) => (
    <div className="mb-2 overflow-x-auto rounded-lg border border-border bg-card last:mb-0">
      <table className="w-full min-w-max border-collapse text-sm">{children}</table>
    </div>
  ),
  thead: ({ children }: { children?: ReactNode }) => (
    <thead className="bg-border/40 text-xs uppercase tracking-wide text-muted-foreground">
      {children}
    </thead>
  ),
  tr: ({ children }: { children?: ReactNode }) => (
    <tr className="border-t border-border first:border-t-0 even:bg-muted/40">{children}</tr>
  ),
  th: ({ children }: { children?: ReactNode }) => (
    <th className="whitespace-nowrap px-3 py-2 text-left font-semibold">{children}</th>
  ),
  td: ({ children }: { children?: ReactNode }) => {
    const texto = nodeToText(children).trim();
    const estado = estadoDeCelda(texto);
    if (estado) {
      const clases =
        estado === 'ok'
          ? 'bg-success/15 text-success'
          : 'bg-destructive/15 text-destructive';
      return (
        <td className="px-3 py-2">
          <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-semibold ${clases}`}>
            {texto}
          </span>
        </td>
      );
    }
    const esNumero = /^[\d.,]+(\s\S+)?$/.test(texto);
    return (
      <td className={`px-3 py-2 ${esNumero ? 'whitespace-nowrap text-right tabular-nums' : ''}`}>
        {children}
      </td>
    );
  },
};

export default function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user';

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-sm bg-primary px-4 py-2 text-sm text-on-primary">
          {message.content}
        </div>
      </div>
    );
  }

  if (message.isError) {
    return (
      <div className="flex justify-start">
        <div className="flex max-w-[85%] items-start gap-2 rounded-2xl rounded-bl-sm border border-destructive/30 bg-destructive/10 px-4 py-2 text-sm text-destructive">
          <WarningCircle size={18} weight="regular" className="mt-0.5 shrink-0" aria-hidden="true" />
          <span>{message.content}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] rounded-2xl rounded-bl-sm bg-muted px-4 py-2 text-sm text-foreground">
        <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
          {message.content}
        </ReactMarkdown>
      </div>
    </div>
  );
}
