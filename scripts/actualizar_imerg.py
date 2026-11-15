"""Robot de Yachachiq: lluvia diaria del satelite GPM IMERG (NASA) para las 6 zonas de Moquegua.

- Baja IMERG Late diario (GPM_3IMERGDL.07) desde Earthdata Cloud por OPeNDAP, con el token de Earthdata
  guardado como secreto EARTHDATA_TOKEN en GitHub (nunca se escribe en el codigo).
- Guarda la serie diaria en imerg_diario.json (se va completando: primero los dias recientes,
  despues la historia desde 2001).
- Escribe imerg.json: lluvia de los ultimos 30 dias con dato y sus percentiles en esas mismas
  fechas de cada ano (2001 en adelante). La app la usa en "Lluvia este mes".
Equipo TROYA - NASA Space Apps 2026.
"""
import datetime as dt, http.cookiejar, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

ZONAS = {
    "Costa (Ilo)": (-17.64, -71.34),
    "Desierto intermedio (Moquegua bajo)": (-17.20, -71.00),
    "Valle de Omate": (-16.67, -70.97),
    "Sierra media (Carumas-Torata)": (-16.81, -70.69),
    "Zona alta norte (Ichuña)": (-16.14, -70.54),
    "Altiplano (represa Pasto Grande)": (-16.73, -70.22),
}
NOMBRES = list(ZONAS)
COLECCION = "C2723754859-GES_DISC"   # GPM_3IMERGDL.07 en Earthdata Cloud (los servidores viejos de GES DISC cerraron en 2026)
OPENDAP = f"https://opendap.earthdata.nasa.gov/collections/{COLECCION}/granules/"
CMR = "https://cmr.earthdata.nasa.gov/search/granules.json"
INICIO = dt.date(2001, 1, 1)
CACHE, SALIDA = "imerg_diario.json", "imerg.json"
PRESUPUESTO = int(os.environ.get("IMERG_DIAS", "400"))   # dias nuevos a bajar en esta corrida
HILOS = int(os.environ.get("IMERG_HILOS", "6"))
LIMITE = time.time() + 60 * int(os.environ.get("IMERG_MINUTOS", "200"))   # deja tiempo para guardar

TOKEN = os.environ.get("EARTHDATA_TOKEN", "").strip()
if not TOKEN:
    print("Falta el secreto EARTHDATA_TOKEN: no se baja IMERG (la app sigue funcionando con POWER).")
    sys.exit(0)

# Indices de la grilla IMERG (0.1 grados; lon -179.95..179.95, lat -89.95..89.95) que cubren las 6 zonas
ilon = lambda x: int(round((x + 179.95) / 0.1))
ilat = lambda y: int(round((y + 89.95) / 0.1))
LO0, LO1 = ilon(min(v[1] for v in ZONAS.values())) - 1, ilon(max(v[1] for v in ZONAS.values())) + 1
LA0, LA1 = ilat(min(v[0] for v in ZONAS.values())) - 1, ilat(max(v[0] for v in ZONAS.values())) + 1


def abridor():
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


ABRIDOR = abridor()


def pedir(url, intentos=3):
    ultimo = None
    for i in range(intentos):
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {TOKEN}", "User-Agent": "yachachiq-robot"})
        try:
            with ABRIDOR.open(req, timeout=90) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code in (401, 403):
                raise SystemExit(f"Earthdata rechazo el token ({e.code}) en {url[:90]}. Revise que el token no haya vencido "
                                 "y que la aplicacion 'NASA GESDISC DATA ARCHIVE' este autorizada en su perfil de Earthdata.")
            ultimo = f"HTTP {e.code}"
        except Exception as e:  # red inestable
            ultimo = repr(e)
        time.sleep(3 * (i + 1))
    print("  no se pudo:", url.split("/")[-1][:60], ultimo)
    return "ERROR"


GRANULOS = {}   # "AAAAMMDD" -> nombre del granulo (la version puede cambiar: V07B, V07C...)


def buscar_granulos(desde, hasta):
    """Pregunta al catalogo CMR de la NASA (publico) que archivos diarios existen entre dos fechas."""
    pagina = 1
    while True:
        q = urllib.parse.urlencode({"collection_concept_id": COLECCION, "page_size": 400, "page_num": pagina,
                                    "temporal": f"{desde}T00:00:00Z,{hasta}T23:59:59Z", "sort_key": "start_date"})
        txt = pedir(f"{CMR}?{q}")
        if txt in (None, "ERROR"):
            return
        ent = json.loads(txt)["feed"]["entry"]
        for e in ent:
            m = re.search(r"3IMERG\.(\d{8})-S000000", e["title"])
            if m:
                GRANULOS[m.group(1)] = e["title"]
        if len(ent) < 400:
            return
        pagina += 1


def leer_ascii(txt):
    """Lee la salida .ascii de OPeNDAP (Earthdata Cloud): lon, lat y una fila de lluvia por cada lon."""
    lon = lat = None; filas = []
    for l in txt.splitlines():
        p = [x.strip() for x in l.split(",")]
        if not p or len(p) < 2:
            continue
        if p[0] == "lon":
            lon = [float(v) for v in p[1:]]
        elif p[0] == "lat":
            lat = [float(v) for v in p[1:]]
        elif p[0].startswith("precipitation.precipitation[") or p[0].startswith("precipitation["):
            filas.append([float(v) for v in p[1:]])
    return lon, lat, filas


def bajar_dia(d):
    if time.time() > LIMITE:
        return d, "ERROR"
    g = GRANULOS.get(d.strftime("%Y%m%d"))
    if not g:
        return d, None
    q = urllib.parse.quote(f"precipitation[0:0][{LO0}:{LO1}][{LA0}:{LA1}],lon[{LO0}:{LO1}],lat[{LA0}:{LA1}]", safe=",")
    txt = pedir(f"{OPENDAP}{urllib.parse.quote(g, safe='')}.ascii?{q}")
    if txt in (None, "ERROR"):
        return d, txt
    lon, lat, filas = leer_ascii(txt)
    if not lon or not lat or len(filas) != len(lon) or any(len(f) != len(lat) for f in filas):
        print("  formato inesperado:", g, txt[:300].replace("\n", " | "))
        return d, "ERROR"
    vals = []
    for nombre in NOMBRES:
        y, x = ZONAS[nombre]
        i = min(range(len(lon)), key=lambda k: abs(lon[k] - x))
        j = min(range(len(lat)), key=lambda k: abs(lat[k] - y))
        v = filas[i][j]
        vals.append(None if v < 0 else round(v, 3))
    return d, vals


def main():
    try:
        cache = json.load(open(CACHE))
    except Exception:
        cache = {"producto": "GPM_3IMERGDL.07 (IMERG Late, diario, mm/dia)", "zonas": NOMBRES, "dias": {}}
    dias = cache["dias"]
    hoy = dt.date.today()
    todos = [INICIO + dt.timedelta(n) for n in range((hoy - INICIO).days)]
    faltan = [d for d in reversed(todos) if d.strftime("%Y%m%d") not in dias]   # primero lo reciente
    tanda = faltan[:PRESUPUESTO]
    print(f"Dias guardados: {len(dias)} | faltan: {len(faltan)} | se bajan ahora: {len(tanda)}")
    if tanda:
        for y in range(min(tanda).year, max(tanda).year + 1):
            buscar_granulos(max(dt.date(y, 1, 1), min(tanda)), min(dt.date(y, 12, 31), max(tanda)))
        print("Archivos IMERG encontrados en el catalogo:", len(GRANULOS))
    nuevos = 0
    with ThreadPoolExecutor(HILOS) as ex:
        for d, vals in ex.map(bajar_dia, tanda):
            k = d.strftime("%Y%m%d")
            if isinstance(vals, list):
                dias[k] = vals; nuevos += 1
            elif vals is None and (hoy - d).days > 20:
                dias[k] = None      # no existe el archivo: no se vuelve a pedir
    cache["dias"] = dict(sorted(dias.items()))
    json.dump(cache, open(CACHE, "w"), separators=(",", ":"))
    print("Dias nuevos:", nuevos)
    escribir_resumen(cache)


def escribir_resumen(cache):
    dias = cache["dias"]
    con = sorted(k for k, v in dias.items() if v and all(x is not None for x in v))
    if not con:
        print("Todavia no hay datos para el resumen."); return
    fin = dt.datetime.strptime(con[-1], "%Y%m%d").date()
    ventana = lambda y: [(dt.date(y, fin.month, fin.day if not (fin.month == 2 and fin.day == 29) else 28)
                          - dt.timedelta(n)).strftime("%Y%m%d") for n in range(30)]

    def suma(y, z):
        v = [dias.get(k) for k in ventana(y)]
        return None if any(x is None or x[z] is None for x in v) else sum(x[z] for x in v)

    def cuantil(a, p):
        s = sorted(a); i = (len(s) - 1) * p; f = int(i)
        return s[f] + (s[min(f + 1, len(s) - 1)] - s[f]) * (i - f)

    zonas = {}
    for z, nombre in enumerate(NOMBRES):
        ll = suma(fin.year, z)
        hist = [s for y in range(INICIO.year + 1, fin.year) if (s := suma(y, z)) is not None]
        if ll is None or len(hist) < 15:
            continue
        zonas[nombre] = dict(ll=round(ll, 1), n_anios=len(hist),
                             **{k: round(cuantil(hist, p), 2) for k, p in
                                (("p10", .10), ("p33", 1 / 3), ("p50", .50), ("p67", 2 / 3), ("p90", .90), ("p95", .95))})
    salida = {"producto": "NASA GPM IMERG Late diario (GPM_3IMERGDL.07), GES DISC",
              "actualizado": dt.date.today().isoformat(),
              "desde": (fin - dt.timedelta(29)).isoformat(), "hasta": fin.isoformat(), "zonas": zonas}
    json.dump(salida, open(SALIDA, "w"), ensure_ascii=False, indent=1)
    print(f"imerg.json: hasta {fin} | zonas con historia suficiente: {len(zonas)}/6")
    for n, v in zonas.items():
        print(f"  {n}: {v}")


if __name__ == "__main__":
    main()
