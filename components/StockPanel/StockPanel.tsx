import { ArrowCounterClockwise, CheckCircle, Warning } from '@phosphor-icons/react/dist/ssr';
import type { Stock } from '@/lib/types';

interface StockPanelProps {
  stock: Stock | null;
  error: string | null;
  overrides: Record<string, number>;
  onChangeOverride: (codigo: string, valor: number | null) => void;
  onReset: () => void;
}

export default function StockPanel({
  stock,
  error,
  overrides,
  onChangeOverride,
  onReset,
}: StockPanelProps) {
  const hasOverrides = Object.keys(overrides).length > 0;

  return (
    <div className="rounded-xl border border-border bg-card p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-foreground">
          Stock actual (insumos críticos)
        </h2>
        {hasOverrides && (
          <button
            type="button"
            onClick={onReset}
            className="flex cursor-pointer items-center gap-1 text-xs text-accent hover:underline"
          >
            <ArrowCounterClockwise size={14} weight="regular" aria-hidden="true" />
            Restaurar
          </button>
        )}
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}
      {!stock && !error && (
        <p className="text-sm text-muted-foreground">Cargando stock…</p>
      )}

      {stock && (
        <>
          <ul className="space-y-3">
            {stock.items.map((item) => {
              const valorActual = overrides[item.codigo] ?? item.stock_actual;
              const bajoMinimo = valorActual < item.stock_minimo;
              return (
                <li key={item.codigo}>
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm text-foreground">{item.insumo}</span>
                    <span
                      className={
                        bajoMinimo
                          ? 'flex items-center gap-1 rounded-full bg-destructive/10 px-2 py-0.5 text-[10px] font-semibold text-destructive'
                          : 'flex items-center gap-1 rounded-full bg-success/10 px-2 py-0.5 text-[10px] font-semibold text-success'
                      }
                    >
                      {bajoMinimo ? (
                        <Warning size={12} weight="bold" aria-hidden="true" />
                      ) : (
                        <CheckCircle size={12} weight="bold" aria-hidden="true" />
                      )}
                      {bajoMinimo ? 'Bajo mínimo' : 'OK'}
                    </span>
                  </div>
                  <div className="mt-1 flex items-center gap-2">
                    <input
                      type="number"
                      min={0}
                      value={valorActual}
                      onChange={(e) => {
                        const num = e.target.valueAsNumber;
                        onChangeOverride(
                          item.codigo,
                          Number.isNaN(num) || num === item.stock_actual
                            ? null
                            : num,
                        );
                      }}
                      className="w-28 rounded-lg border border-border bg-background px-2 py-1 text-sm tabular-nums text-foreground outline-none transition-colors duration-200 focus:border-accent"
                      aria-label={`Stock actual de ${item.insumo}`}
                    />
                    <span className="text-xs tabular-nums text-muted-foreground">
                      {item.unidad} · mín. {item.stock_minimo}
                    </span>
                  </div>
                </li>
              );
            })}
          </ul>
          <p className="mt-4 text-[11px] leading-snug text-muted-foreground">
            Actualizado: {stock.fecha_actualizacion}. Editá los valores para
            simular otro escenario de stock: el cambio aplica solo a esta
            sesión y se envía con cada consulta.
          </p>
        </>
      )}
    </div>
  );
}
