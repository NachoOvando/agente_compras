export interface StockItem {
  codigo: string;
  insumo: string;
  unidad: string;
  stock_actual: number;
  stock_minimo: number;
}

export interface Stock {
  fecha_actualizacion: string;
  items: StockItem[];
}

export interface AskResult {
  answer: string;
  sources: { index: number; score: number }[];
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  isError?: boolean;
}

export type ApiResponse<T> = { data: T } | { error: string; code: string };
