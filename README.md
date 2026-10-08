# MLB KAIZEN

Herramienta reproducible de análisis prepartido de MLB. El flujo práctico es:

`inputs → baseline → Monte Carlo → comparación contra mercado → salida de máquina → pick humano → resultado → Humano vs Máquina`.

La validación estadística se mantiene separada del cálculo: un modelo experimental puede mostrar sus
números, pero esos números deben quedar etiquetados como experimentales hasta completar un backtest
point-in-time real.

## Modos de análisis

- `live`: información obtenida de proveedores.
- `snapshot`: información previamente guardada.
- `manual`: datos introducidos por el usuario.
- `hybrid`: mezcla explícita de fuentes.

El modo manual/híbrido permite introducir un pitcher proyectado que el analista conoce antes de que
el proveedor lo marque como confirmado. El sistema registra el dato como `MANUAL`, no como confirmación
oficial.

## Instalación

Python 3.11+.

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -e ".[all]"
```

## Comandos útiles

```bash
mlb-kaizen init-db
mlb-kaizen status
mlb-kaizen analyze --input examples/analysis-input.manual.example.json --mode manual
mlb-kaizen leaderboard
```

Para entrenamiento/evaluación:

```bash
mlb-kaizen train-model --dataset PATH.jsonl --model poisson --output artifacts/poisson
mlb-kaizen backtest --dataset PATH.jsonl --model poisson --min-train 30 --test-window 10 --calibrate
```

La suite de desarrollo:

```bash
python3 -m unittest discover -s tests -t . -v
python3 scripts/verify.py
```

## Interfaz visual en Google Colab

Para uso sin PowerShell, abre
[`notebooks/MLB_KAIZEN_Control_Center.ipynb`](notebooks/MLB_KAIZEN_Control_Center.ipynb)
en Google Colab. El Control Center conserva tus datos en Google Drive y ofrece
calendario, selector de juego, formulario de cuotas, historial gráfico y
registro de resultados. Instrucciones: [docs/colab-control-center.md](docs/colab-control-center.md).

## Estado

El estado operativo se encuentra en `STATUS.md`. Para recuperación después de una ventana de contexto,
leer `AGENTS.md`/`CLAUDE.md`, `STATUS.md` y Git. `HANDOFF.md` es histórico y no se relee por defecto.

## Evidencia

Los fixtures sintéticos y ejemplos manuales sirven para verificar el código, no para afirmar precisión
real. La validación empírica requiere datos históricos reales con timestamps point-in-time.
