"""Herramientas que el LLM puede invocar (function calling de OpenAI).

Todo cálculo numérico vive acá, en Python. El modelo se limita a extraer los
parámetros de la pregunta (cantidad de pares, talle, si se aplica la curva),
que es lo que hace bien; la aritmética la hace el código, que no se equivoca
ni arrastra números de turnos anteriores.

Sin esto el modelo tomaba un total ya calculado del historial y lo volvía a
multiplicar (1000 pares → 497.337 g → "× 1000" → 497.337.000 g), concluyendo
que faltaba stock cuando en realidad sobraba 20 veces.
"""

from engine import config, context

NOMBRE_CALCULAR = "calcular_necesidad_insumos"

TOOLS_SPEC = [
    {
        "type": "function",
        "function": {
            "name": NOMBRE_CALCULAR,
            "description": (
                "Calcula la necesidad exacta de cada insumo crítico para una orden "
                "de N pares del producto y la compara contra el stock actual. Usala "
                "SIEMPRE que la pregunta (o el historial de la conversación) "
                "mencione una cantidad de pares a producir: nunca hagas vos mismo "
                "la multiplicación ni reutilices un total de un turno anterior."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "cantidad_pares": {
                        "type": "integer",
                        "description": (
                            "Cantidad total de pares a producir, tal como la indica "
                            "el usuario. Es la cantidad de la orden completa, no una "
                            "cantidad por talle."
                        ),
                    },
                    "talle": {
                        "type": "string",
                        "description": (
                            "Talle puntual (del 34 al 50) si el usuario lo "
                            "especificó. Omitir si la orden no indica un talle."
                        ),
                    },
                    "aplicar_curva_normal": {
                        "type": "boolean",
                        "description": (
                            "true SOLO si el usuario confirmó explícitamente que se "
                            "aplique la curva normal de talles. Nunca lo asumas por "
                            "tu cuenta."
                        ),
                    },
                },
                "required": ["cantidad_pares"],
            },
        },
    }
]


def _normalizar_talle(talle) -> str:
    """'T40', 't 40', 40 → '40'. El modelo manda el talle en formatos variados."""
    return str(talle).strip().upper().lstrip("T").strip()


def calcular_necesidad_insumos(
    cantidad_pares, talle=None, aplicar_curva_normal: bool = False,
    stock_overrides: dict[str, float] | None = None,
) -> dict:
    """Necesidad de cada insumo crítico para una orden de N pares vs. stock.

    Devuelve siempre un dict serializable a JSON. Si la orden no trae talle ni
    confirmación de la curva y hay insumos de consumo variable por talle,
    devuelve `necesita_aclaracion` SIN ningún número: el "preguntá antes de
    asumir" queda garantizado por código, no por una regla del prompt.
    """
    try:
        cantidad_pares = int(cantidad_pares)
    except (TypeError, ValueError):
        return {"error": "La cantidad de pares tiene que ser un número entero."}
    if cantidad_pares <= 0:
        return {"error": "La cantidad de pares tiene que ser mayor a cero."}

    bom = context.load_bom()
    criticos = [fila for fila in bom if fila["critico"]]
    variables = [fila for fila in criticos if fila.get("consumo_por_talle")]

    if talle is not None:
        talle = _normalizar_talle(talle)
        if talle not in config.TALLES:
            return {
                "error": (
                    f"El talle '{talle}' está fuera del rango disponible "
                    f"(T{config.TALLES[0]} a T{config.TALLES[-1]})."
                )
            }

    if variables and talle is None and not aplicar_curva_normal:
        return {
            "necesita_aclaracion": True,
            "motivo": (
                "La orden no indica talle y hay insumos críticos cuyo consumo por "
                "par cambia según el talle, así que todavía no se puede calcular "
                "la necesidad."
            ),
            "insumos_con_consumo_variable": [fila["insumo"] for fila in variables],
            "opciones": [
                "aplicar la curva normal de talles a la cantidad total",
                "indicar un talle puntual para toda la orden",
            ],
        }

    ponderado = {
        fila["codigo"]: fila["consumo_ponderado_por_par"]
        for fila in context.compute_consumo_ponderado_curva(
            bom, context.load_curva_talles()
        )
    }
    stock_por_codigo = {
        item["codigo"]: item for item in context.load_stock(stock_overrides)["items"]
    }

    insumos = []
    for fila in criticos:
        if fila.get("consumo_por_talle"):
            if talle is not None:
                consumo = fila["consumo_por_talle"][talle]
                base = f"consumo del talle {talle}"
            else:
                consumo = ponderado[fila["codigo"]]
                base = "consumo ponderado por la curva normal de talles"
        else:
            consumo = fila["consumo_por_unidad"]
            base = "consumo fijo por par (no varía según el talle)"

        necesidad = round(cantidad_pares * consumo, 2)
        detalle = {
            "insumo": fila["insumo"],
            "unidad": fila["unidad"],
            "consumo_por_par": consumo,
            "base_del_consumo": base,
            "necesidad": necesidad,
        }

        item = stock_por_codigo.get(fila["codigo"])
        if item is None:
            detalle["stock_actual"] = None
            detalle["alcanza"] = None
            detalle["nota"] = "No hay stock registrado para este insumo."
        else:
            actual = item["stock_actual"]
            alcanza = actual >= necesidad
            detalle["stock_actual"] = actual
            detalle["alcanza"] = alcanza
            detalle["faltante"] = 0 if alcanza else round(necesidad - actual, 2)
        insumos.append(detalle)

    if talle is not None:
        base_general = f"talle {talle} para toda la orden"
    elif variables:
        base_general = "curva normal de talles"
    else:
        base_general = "consumo fijo por par"

    return {
        "cantidad_pares": cantidad_pares,
        "base_del_calculo": base_general,
        "insumos": insumos,
    }


def ejecutar(nombre: str, argumentos: dict,
             stock_overrides: dict[str, float] | None = None) -> dict:
    """Despacha una tool call del LLM. Nunca lanza: los errores viajan como
    dato para que el modelo los pueda explicar en la respuesta."""
    if nombre != NOMBRE_CALCULAR:
        return {"error": f"Herramienta desconocida: '{nombre}'."}
    return calcular_necesidad_insumos(
        cantidad_pares=argumentos.get("cantidad_pares"),
        talle=argumentos.get("talle"),
        aplicar_curva_normal=bool(argumentos.get("aplicar_curva_normal", False)),
        stock_overrides=stock_overrides,
    )
