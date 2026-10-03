# AGENTS.md — MLB KAIZEN

Reglas críticas. Detalle extenso vive en `docs/`, no aquí.

## Al empezar una sesión

1. Lee `STATUS.md` (no `HANDOFF.md` completo).
2. `git status --short && git log -5 --oneline`
3. Si `STATUS.md` contradice el código/tests → el código y los tests ganan.
   Corrige `STATUS.md`, no al revés.
4. Lee `docs/AI_REPO_MAP.md` solo si necesitas ubicar algo específico.
5. Abre `HANDOFF.md` solo si `STATUS.md` no alcanza para reconstruir el estado.

## Jerarquía de verdad

```
1. Código actual
2. Tests actuales
3. STATUS.md
4. .agent/checkpoint.json
5. docs/design-decisions.md
6. docs/features/*.md (ficha específica)
7. docs/AI_REPO_MAP.md
8. README.md
9. HANDOFF.md histórico
```

## Reglas no negociables (resumen — detalle en HANDOFF.md sección 1-2)

- Nunca inventar datos, estadísticas, cuotas, resultados. Estado desconocido →
  `DATA_NOT_VERIFIED` / `NOT_AVAILABLE` / `NOT_YET_PUBLISHED`, nunca un valor
  por defecto disfrazado de dato real.
- Point-in-time siempre: `retrieved_at` de una feature derivada hereda el de
  su fuente cruda, nunca la hora del cómputo.
- Toda fórmula de feature/mercado nueva: ficha en `docs/` + versión
  (`FORMULA_VERSION` o equivalente) + test. Cambiar la fórmula = nueva
  versión, nunca sobrescribir silenciosamente.
- Separar `CALCULATION STATUS` / `DATA QUALITY STATUS` / `MODEL VALIDATION
  STATUS` — "no calibrado" no es lo mismo que "no puede calcular".
- No `--force` genérico que desactive todas las validaciones. Modos
  explícitos (`live`/`snapshot`/`manual`/`hybrid`) en su lugar.
- Nunca afirmar rentabilidad futura. `model_edge ≠ proven profitable edge`.

## Cómo trabajar

- Bloques pequeños, testeables, un commit por bloque cerrado.
- Antes de integrar un proveedor externo nuevo: verificar campos, auth,
  límites, licencia — documentarlo aunque sea parcial (ver sección 16/18 del
  HANDOFF como ejemplo de cómo documentar una verificación incompleta con
  honestidad, no ocultarla).
- Un hueco de diseño encontrado a mitad de tarea se corrige ahí mismo, no se
  pospone silenciosamente — se documenta en `docs/design-decisions.md` si es
  una decisión, o en el commit si es una corrección menor.

## Cómo verificar

```bash
cd "MLB KAIZEN"
python3 -m unittest discover -s tests -t . -v   # suite completa
python3 -m unittest tests.test_run_profile -v    # un módulo específico
python3 -m compileall -q mlb_kaizen tests        # solo compilación
```

Suite completa obligatoria cuando: cambia dominio, cambia schema/migración,
cambia una API pública, se cierra una fase, se crea checkpoint. Un módulo
específico alcanza para un cambio aislado sin riesgo de regresión global.

`pytest` puede no estar disponible sin red en el entorno de ejecución —
`unittest discover` es el fallback documentado y válido.

## Recuperación tras agotar contexto

No pidas al usuario que reexplique el proyecto. Ejecuta la secuencia de
"Al empezar una sesión" arriba. Solo si `STATUS.md` no permite reconstruir el
estado, lee `HANDOFF.md` completo.

- Secrets: prefer authenticated request headers over query parameters whenever the provider supports them,
  so credentials do not enter cache keys or persisted URL metadata.
