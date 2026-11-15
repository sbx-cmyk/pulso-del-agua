# Yachachiq · Moquegua

*Yachachiq* is Quechua for "the one who knows and teaches what they know" (formerly "Pulso del Agua").

App gratuita para agricultores de Moquegua (Perú): les dice cómo está la lluvia y el calor en su zona y qué hacer en su chacra. Tiene íconos grandes, voz y cuatro idiomas: castellano, inglés, quechua y aimara (estos dos últimos son un borrador en revisión).

NASA Space Apps Challenge 2026, reto "Be An Earth System Trend Detective!". Equipo TROYA, Universidad Nacional de Moquegua (UNAM).

- App: `index.html`
- Página técnica para revisores: `tecnico.html`
- Voces grabadas: carpeta `voz/`

Datos: NASA POWER (MERRA-2), NASA GPM IMERG (vía Giovanni), índices de El Niño de NOAA CPC. Mapa: © colaboradores de OpenStreetMap.

Use of AI: code, icons, illustrations (marked "AI" in the app) and the Yachachiq and TROYA logos were made with the help of AI tools (Claude and others) and reviewed by Team TROYA. The demo video is AI-assisted and carries a visible AI watermark. The recorded voices in `voz/` were generated with AI text-to-speech (ElevenLabs and LuvVoice). Quechua and Aymara texts are AI-assisted drafts pending review by native speakers.

## Se actualiza solo cada día
- En el celular de cada agricultor, una vez al día, la app baja los datos diarios de NASA POWER (1981 hasta hoy), recalcula "Hoy en su zona" (temperatura y heladas de los últimos 30 días frente a 45 años) y **re-entrena el modelo de temperatura del próximo mes** (mes + tendencia + El Niño).
- Un robot de GitHub Actions (`.github/workflows/actualizar_datos.yml`) baja cada mañana el índice de El Niño (ONI) de NOAA a `oni.json`.
- El mismo robot baja cada día la lluvia del satélite **GPM IMERG** de la NASA (con el token de Earthdata guardado como secreto `EARTHDATA_TOKEN`) a `imerg.json`; la app la usa en "Lluvia este mes". Si no está, usa POWER con su control de dato dudoso.
