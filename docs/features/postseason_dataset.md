# Constructor point-in-time de playoffs E12

Implementación: `build_postseason_point_in_time_rows` en
`mlb_kaizen.training.build_dataset`.

El constructor emite filas sólo para objetivos de playoffs `F/D/L/W`. Para
crear sus 13 features E3+E7+E8 admite como historia únicamente partidos de
temporada regular o playoffs (`R/F/D/L/W`) de la **misma temporada** y con
inicio estrictamente anterior. `S`, `E`, `A`, tipos desconocidos y el propio
partido no pueden entrar en ningún acumulado.

Los partidos con la misma hora de inicio se calculan como un grupo y se añaden
al historial sólo al terminar ese grupo. Esto impide que el marcador final de
un partido simultáneo parezca disponible antes del otro. Todos los acumulados,
incluidos fuerza de rivales y forma reciente, se reinician al iniciar una nueva
temporada.

No entrena ni calibra un modelo. Es sólo la preparación verificable de inputs
para el protocolo E12 pre-registrado.
