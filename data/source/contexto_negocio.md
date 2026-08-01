# Contexto operativo del negocio

Fabricante argentino de calzado de seguridad industrial, con más de 60 años
en el mercado. Produce internamente sus componentes semielaborados
(capelladas, plantillas) y compra externamente los insumos críticos.

## Curva de ventas por talle

La demanda pronosticada a nivel artículo (salida de un modelo de forecasting
estadístico) se desagrega por talle mediante una distribución normal, NO
uniforme. El talle medio (moda de la curva) es el **42**. La curva se aplica
como distribución de probabilidad por talle, normalizada a suma 1, y se
multiplica por el forecast mensual del artículo para obtener unidades por
talle; esa desagregación es la que después se cruza contra la BOM para
calcular el consumo proyectado de cada insumo.

Implicancia: el consumo de un insumo **no es lineal** con el volumen total
vendido — los talles extremos (35-36, 46-47) consumen mucho menos material
que los talles centrales (40-43), aunque el artículo sea el mismo. Por eso
nunca hay que promediar ni prorratear linealmente una cantidad de pares
entre talles.

## Metodología de criticidad de insumos

Los insumos del producto (decenas de SKUs, diferenciados por talle) se
consolidan en familias de compra (mismo insumo, distintos talles = una sola
decisión de compra). Sobre esas familias se aplicó un modelo de clustering
(K-Means, K=3) con dos variables: volumen relativo normalizado dentro de su
unidad de medida, y alcance productivo (% de artículos que usan ese insumo).
Los clusters resultantes son: CRÍTICO / IMPORTANTE / SECUNDARIO.

De las familias más críticas, se seleccionaron 3 para gestión de inventario
activa (las que hoy tiene este asistente) por combinar alta criticidad con
dependencia de un proveedor externo puntual:

- **Conjunto Sistema PU**: va en el 100% de los artículos de la línea
  (alcance productivo total), depende de un proveedor único.
- **Puntera de Acero 59 Normal**: se fabrica a pedido (make-to-order), no
  hay stock del proveedor para comprar "ya".
- **Cajas de Empaque** (variantes bota/botín): impresión personalizada por
  proveedor, no son cajas genéricas reemplazables por otro proveedor rápido.

## Insumos fuera de este alcance (y por qué)

- **Plantillas y capelladas**: son semielaborados de producción interna, no
  compras externas — no aplica gestión de inventario de proveedor.
- Otras variantes de insumos que comparten proveedor y proceso de
  abastecimiento con alguno de los 3 insumos ya gestionados no se gestionan
  por separado.
- **Cordones y ojalillos**: lead time corto (alrededor de 1 semana) y
  múltiples proveedores locales disponibles — se gestionan con una política
  reactiva simple (reponer cuando se necesita), no con seguimiento
  predictivo ni con el modelo de criticidad. Si preguntan por estos
  insumos, la respuesta correcta es explicar que se gestionan de forma
  reactiva, no que "no hay información".

## Qué significa "insumo crítico" en este asistente

Es específicamente el conjunto de 3 insumos de la sección anterior — no es
sinónimo de "insumo importante en general". El resto de los insumos de la
BOM (críticos o no según este análisis) no tienen ficha de proveedor, stock
ni política de inventario cargados en este sistema.
