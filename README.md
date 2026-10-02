# MLB KAIZEN

Base reproducible para análisis cuantitativo de MLB. La primera entrega es un
vertical slice deliberadamente conservador: datos con procedencia, validación,
mercado, almacenamiento inmutable, un modelo de carreras transparente y una
simulación reproducible. No emite una recomendación de apuesta si faltan datos
críticos o calibración temporal.

## Principios

- Datos observados, estimaciones del modelo y precios de mercado permanecen separados.
- Las predicciones se guardan como observaciones inmutables con versiones y timestamps.
- Las cuotas se convierten primero a decimal; EV y Kelly nunca operan directamente sobre
  cuotas americanas.
- El modelo base es una hipótesis verificable, no una afirmación de rentabilidad.
- La calibración y el backtest walk-forward son requisitos antes de habilitar señales.

## Instalación

Requiere Python 3.11 o superior.

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -e ".[dev]"
python -m pytest
```

En Colab/Jupyter puede usar `pip install -e .` desde el directorio del proyecto.

## Comandos iniciales

```bash
mlb-kaizen init-db
mlb-kaizen health
mlb-kaizen schedule --date 2026-09-16
```

`schedule` usa el endpoint público de MLB Stats API y guarda la respuesta en caché con
timestamp. La documentación disponible para ese endpoint es comunitaria; por ello el
adaptador registra la procedencia y trata cualquier fallo como `DATA NOT VERIFIED`, no
como ausencia de juegos. Antes de automatizar mercados, Statcast, clima, lesiones o
lineups deben verificarse sus proveedores, términos y campos.

## Estado de implementación

Implementado ahora:

- configuración por ambiente, caché HTTP con reintentos y timeout;
- adaptador de calendario MLB;
- modelos de procedencia y disponibilidad de datos;
- SQLite para snapshots, cuotas, predicciones y resultados;
- validadores de datos y puerta de calidad;
- conversión de cuotas, no-vig proporcional, EV y Kelly;
- modelo base de carreras con supuestos explícitos;
- Monte Carlo Negativa Binomial con semilla;
- pruebas unitarias de los componentes anteriores.

Pendiente y bloqueado hasta disponer de fuentes verificadas e históricos con timestamp:
Statcast, lineups, pitchers, bullpen, clima, proveedor de cuotas, entrenamiento,
calibración temporal, CLV y backtesting walk-forward.
