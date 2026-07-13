"""Tests del prompt engineering: reglas del cerco presentes en el system prompt."""

from engine import prompts


def test_system_prompt_define_el_cerco():
    sp = prompts.SYSTEM_PROMPT
    assert "ÚNICAMENTE" in sp
    assert "No tengo esa información disponible" in sp
    assert "stock mínimo" in sp
    assert "lead time" in sp


def test_user_prompt_combina_contexto_y_pregunta():
    up = prompts.build_user_prompt("¿Cuál es el lead time?", "CTX-DE-PRUEBA")
    assert "CTX-DE-PRUEBA" in up
    assert "¿Cuál es el lead time?" in up
    assert up.index("CTX-DE-PRUEBA") < up.index("¿Cuál es el lead time?")
