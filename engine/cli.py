"""CLI del asistente: modo demo (preguntas predefinidas) y modo interactivo.

Uso:
    python -m engine.cli demo          # corre las preguntas de ejemplo
    python -m engine.cli               # loop interactivo (salir/exit para terminar)
"""

import sys

from engine.config import PREGUNTAS_DEMO
from engine.generate import rag_answer


def _responder(pregunta: str) -> None:
    print(f"\nPREGUNTA: {pregunta}")
    resultado = rag_answer(pregunta)
    print(f"RESPUESTA:\n{resultado['answer']}")
    print("-" * 60)


def modo_demo() -> None:
    print("=== MODO DEMO: preguntas de ejemplo ===")
    for pregunta in PREGUNTAS_DEMO:
        _responder(pregunta)


def modo_interactivo() -> None:
    print("Asistente de compras Maincal. Escribí 'salir' para terminar.\n")
    while True:
        pregunta = input("Tu pregunta: ").strip()
        if pregunta.lower() in ("salir", "exit", "quit", ""):
            print("Hasta luego.")
            break
        _responder(pregunta)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "demo":
        modo_demo()
    else:
        modo_interactivo()
