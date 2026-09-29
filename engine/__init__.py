"""Motor RAG del asistente de compras.

Paquete independiente del framework web: toda la lógica de recuperación,
armado de contexto y generación vive acá, y es testeable sin levantar
un servidor. La API (api/index.py) y la CLI (engine/cli.py) son capas
finas sobre este motor.
"""
