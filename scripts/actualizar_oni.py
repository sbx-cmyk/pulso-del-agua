"""Baja el indice ONI (El Nino) de NOAA y lo guarda en oni.json para que la app re-entrene su modelo cada dia.
Lo corre GitHub Actions todos los dias (.github/workflows/actualizar_datos.yml). Equipo TROYA - Yachachiq."""
import json, datetime, urllib.request

URL = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"
ORDEN = ["DJF", "JFM", "FMA", "MAM", "AMJ", "MJJ", "JJA", "JAS", "ASO", "SON", "OND", "NDJ"]

texto = urllib.request.urlopen(URL, timeout=60).read().decode()
filas = []
for linea in texto.strip().splitlines()[1:]:
    p = linea.split()
    if len(p) >= 4 and p[0] in ORDEN and int(p[1]) >= 1981:
        filas.append([int(p[1]), ORDEN.index(p[0]) + 1, float(p[3])])
if len(filas) < 500:
    raise SystemExit(f"ONI incompleto ({len(filas)} filas): no se cambia nada")

nuevo = {"fuente": "NOAA CPC ONI (oni.ascii.txt); mes central del trimestre movil",
         "actualizado": datetime.date.today().isoformat(), "oni": filas}
try:
    viejo = json.load(open("oni.json"))
except Exception:
    viejo = {}
if viejo.get("oni") == filas:
    print("ONI sin cambios. Ultimo:", filas[-1])
else:
    json.dump(nuevo, open("oni.json", "w"), separators=(",", ":"))
    print("ONI actualizado. Ultimo:", filas[-1])
