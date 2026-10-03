# Contrato de input para `analyze`

`analyze` recibe un documento JSON validable contra
`docs/schemas/analysis-input.schema.json`.

El documento describe el **information set** disponible antes del partido.
Los perfiles ya deben venir normalizados desde Feature Store; el comando no
inventa índices.

`mode` distingue la procedencia del conjunto de información:

- `live`: datos obtenidos de proveedores en tiempo de ejecución;
- `snapshot`: datos históricos/locales previamente guardados;
- `manual`: inputs introducidos por el usuario;
- `hybrid`: combinación de fuentes y overrides manuales explícitos.

El promedio `league_runs_per_team` es obligatorio y debe corresponder al mismo
season/information set que los perfiles. Un número usado solo como fixture o
demo debe quedar identificado como tal y no como dato MLB real.

El análisis puede calcularse con `MODEL: EXPERIMENTAL`. Esto no significa que el
modelo esté validado; significa que sus salidas todavía deben pasar
a backtesting/calibración temporal antes de interpretarse como evidencia de
performance predictiva.
