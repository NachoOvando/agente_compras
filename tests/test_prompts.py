"""Tests del prompt engineering: reglas del cerco presentes en el system prompt."""

from engine import prompts


def test_system_prompt_define_el_cerco():
    sp = prompts.SYSTEM_PROMPT
    assert "ÚNICAMENTE" in sp
    assert "No tengo esa información disponible" in sp
    assert "stock mínimo" in sp
    assert "lead time" in sp


def test_system_prompt_aclara_que_bom_cubre_insumos_no_criticos():
    """La BOM se inyecta completa (críticos y no); el prompt no debe hacer
    que el modelo rechace consultas de consumo de insumos no críticos."""
    sp = prompts.SYSTEM_PROMPT
    assert "no críticos" in sp
    assert "TODOS los insumos" in sp


def test_system_prompt_pregunta_antes_de_asumir_curva_o_talle():
    """No debe promediar/asumir talle: tiene que preguntar curva normal vs.
    talle puntual antes de calcular (bug real visto con un LLM en producción)."""
    sp = prompts.SYSTEM_PROMPT
    assert "curva normal" in sp
    assert "talle puntual" in sp
    assert "esperá la respuesta del usuario" in sp


def test_system_prompt_no_expone_el_calculo_y_pide_tablas():
    """La respuesta visible no debe narrar el procedimiento interno (pasos,
    cuentas) ni un párrafo cuando hay varios insumos/talles: tiene que ir
    directo al resultado en una tabla (bug real: el modelo mostraba "1.
    Listado de insumos...", "2. Cálculo: 200 × 464.167 = ...")."""
    sp = prompts.SYSTEM_PROMPT
    assert "NUNCA lo muestres en la respuesta" in sp
    assert "tabla markdown" in sp
    assert "no el desarrollo de la cuenta" in sp


def test_system_prompt_usa_consumo_ponderado_en_vez_de_sumar_por_talle():
    """Bug real: al aplicar la curva normal, el modelo sumaba mal 17 términos
    (multiplicaba el % directo por la cantidad de pares y lo llamaba el
    resultado, sin aplicar el consumo real por talle). Ahora el prompt tiene
    que usar el consumo ponderado ya calculado en Python (una multiplicación,
    no una suma de 17 términos)."""
    sp = prompts.SYSTEM_PROMPT
    assert "CONSUMO PONDERADO" in sp
    assert "NUNCA repartas la cantidad por talle ni sumes 17 términos" in sp


def test_user_prompt_combina_contexto_y_pregunta():
    up = prompts.build_user_prompt("¿Cuál es el lead time?", "CTX-DE-PRUEBA")
    assert "CTX-DE-PRUEBA" in up
    assert "¿Cuál es el lead time?" in up
    assert up.index("CTX-DE-PRUEBA") < up.index("¿Cuál es el lead time?")
