# Control Center visual de Google Colab

El notebook [`notebooks/MLB_KAIZEN_Control_Center.ipynb`](../notebooks/MLB_KAIZEN_Control_Center.ipynb)
es la interfaz visual de MLB KAIZEN. No sustituye el motor: utiliza las mismas
clases de calendario, almacenamiento append-only, cuotas y resultado final.

## Inicio

1. En GitHub, abre el archivo del notebook y elige **Open in Colab** (o súbelo
   manualmente a Google Colab).
2. Ejecuta la primera celda y autoriza exclusivamente el acceso a tu Google
   Drive cuando Colab lo solicite.
3. Ejecuta la celda **Control Center**. No necesitas instalar Python, Git ni
   abrir PowerShell.

Cuando el notebook reciba una actualización, vuelve a ejecutar primero la
celda de preparación y después la celda **Control Center**. La primera muestra
el commit descargado y limpia módulos viejos de la memoria de Colab.

El código se descarga desde GitHub en la máquina temporal de Colab. Las cuotas,
resultados, caché y artefactos se guardan bajo `MyDrive/MLB_KAIZEN/`, de modo
que sobreviven al cierre de la sesión de Colab.

## Qué automatiza

- Consulta el calendario oficial de MLB para una fecha elegida.
- Presenta los juegos en un selector visual y guarda el snapshot del
  calendario.
- Convierte momios americanos y registra cada cuota visible sin sobrescribir
  capturas anteriores.
- Muestra una tabla y gráfica de las cuotas capturadas del juego elegido.
- En playoffs, muestra la probabilidad que implica el mercado sin margen sólo
  si ambos lados de una misma casa, mercado, línea y hora están capturados.
- Guarda un marcador final que el usuario confirme como oficial.

## Límites intencionales

- La casa de apuestas no se consulta automáticamente: el usuario introduce el
  precio que vio. Eso evita inventar, extraer sin permiso o atribuir una cuota
  a una fuente no verificada.
- E11 sólo se ejecuta para `game_type=R` antes del inicio y requiere su
  artefacto local confiable en Drive. El notebook no reentrena, no crea un
  sustituto y bloquea playoffs.
- La interfaz no transforma una probabilidad, una gráfica de cuotas ni una
  diferencia contra el mercado en recomendación o prueba de rentabilidad.

## Pestaña de playoffs

La pestaña **Playoffs / mercado** no desbloquea el modelo E11 ni crea un modelo
de playoffs. Muestra una *referencia de mercado sin margen proporcional*: toma
los dos precios opuestos de una misma observación y normaliza sus probabilidades
implícitas para que sumen 100%. Si falta un lado, si la hora no coincide o si
las líneas pertenecen a distintos mercados, no calcula un porcentaje; mezclar
capturas sería inventar una referencia que no existió.
