import AsistenteCompras from '@/components/AsistenteCompras/AsistenteCompras';
import { appConfig } from '@/lib/app-config';

export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-6xl flex-col gap-6 px-4 py-8">
      <header>
        <h1 className="text-2xl font-bold tracking-tight">
          Asistente de Compras — Maincal S.A.
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Recomendaciones de compra de insumos críticos del{' '}
          {appConfig.producto}, respondiendo únicamente con datos de la empresa
          (fichas de proveedores, BOM y stock actual).
        </p>
      </header>
      <AsistenteCompras />
    </main>
  );
}
