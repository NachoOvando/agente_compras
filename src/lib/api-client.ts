import type { ApiResponse, AskResult, HistoryTurn, Stock } from './types';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  let body: ApiResponse<T>;
  try {
    body = (await res.json()) as ApiResponse<T>;
  } catch {
    throw new Error('El servidor devolvió una respuesta inválida.');
  }
  if ('error' in body) {
    throw new Error(body.error);
  }
  if (!res.ok) {
    throw new Error('Error inesperado del servidor.');
  }
  return body.data;
}

export function fetchStock(): Promise<Stock> {
  return request<Stock>('/api/py/stock');
}

export function askQuestion(
  question: string,
  stockOverrides?: Record<string, number>,
  history?: HistoryTurn[],
): Promise<AskResult> {
  return request<AskResult>('/api/py/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, stockOverrides, history }),
  });
}
