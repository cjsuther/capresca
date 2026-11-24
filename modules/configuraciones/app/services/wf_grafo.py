"""Grafo de un workflow de aprobaciones: validación, proyección al motor actual, diff y conversión.

Funciones PURAS (sin DB ni HTTP): reciben y devuelven dicts. El editor del frontend tiene un espejo
de `validar` en `frontend/src/modules/configuraciones/workflow/grafo.js` con los MISMOS códigos de
problema: la validación del frontend es para dar feedback en vivo; la de acá es la que manda.

Formato (schema 1):

    {"schema": 1,
     "nodos": [{"id": "n1", "tipo": "inicio|aprobacion|decision|notificacion|fin", "nombre": "...",
                # aprobacion:
                "asignar": {"tipo": "rol", "valor": "APROBAR"} | {"tipo": "grupo", "valor": "Gerencia", "id": 3},
                "incluir": ["usuario"], "excluir": ["usuario"], "cuatroOjos": true,
                # notificacion:
                "destinatarios": [{"tipo": "rol|grupo|usuario|iniciador", "valor": "..."}], "mensaje": "...",
                # fin:
                "resultado": "APROBADO|RECHAZADO"}],
     "conexiones": [{"id": "c1", "de": "n1", "a": "n2",
                     "salida": "aprobado|rechazado",            # sólo desde una aprobación
                     "condicion": {"modo": "todas|alguna", "reglas": [{"variable": "monto", "op": ">", "valor": 5}]},
                     "defecto": true}]}                         # sólo desde una decisión

La posición de cada nodo NO es parte del grafo (va en `layout`): mover una caja no cambia la versión.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict

SCHEMA = 1
TIPOS = ("inicio", "aprobacion", "decision", "notificacion", "fin")
ROLES = ("APROBAR", "SUPERVISAR")           # permisos `<modulo>:aprobaciones:aprobar|supervisar`
RESULTADOS = ("APROBADO", "RECHAZADO")
SALIDAS_APROBACION = ("aprobado", "rechazado")
TIPOS_DESTINATARIO = ("rol", "grupo", "usuario", "iniciador")
OPERADORES = {
    "numero": ("=", "!=", ">", ">=", "<", "<="),
    "texto": ("=", "!=", "contiene"),
    "opcion": ("=", "!=", "en"),
    "booleano": ("=",),
}
MAX_NODOS = 200


def _p(codigo: str, mensaje: str, nodo: str | None = None, conexion: str | None = None,
       nivel: str = "error") -> dict:
    return {"codigo": codigo, "nivel": nivel, "mensaje": mensaje, "nodo": nodo, "conexion": conexion}


def _nombre(n: dict) -> str:
    return (n.get("nombre") or "").strip() or n.get("tipo", "nodo")


# ── Validación ───────────────────────────────────────────────────────────────────────────────────
def validar(grafo: dict, variables: dict | None = None) -> list[dict]:
    """Problemas del grafo: lista de {codigo, nivel: error|aviso, mensaje, nodo, conexion}.
    Sin errores (puede haber avisos) = se puede publicar, si además es compatible con el motor."""
    variables = variables or {}
    probs: list[dict] = []
    nodos = grafo.get("nodos") or []
    conexiones = grafo.get("conexiones") or []

    if len(nodos) > MAX_NODOS:
        return [_p("DEMASIADOS_NODOS", f"El workflow no puede tener más de {MAX_NODOS} nodos.")]

    por_id: dict[str, dict] = {}
    for n in nodos:
        nid = n.get("id")
        if not nid or not isinstance(nid, str):
            probs.append(_p("NODO_SIN_ID", "Hay un nodo sin identificador."))
            continue
        if nid in por_id:
            probs.append(_p("ID_DUPLICADO", f"Hay dos nodos con el id «{nid}».", nodo=nid))
            continue
        if n.get("tipo") not in TIPOS:
            probs.append(_p("TIPO_INVALIDO", f"Tipo de nodo desconocido: {n.get('tipo')!r}.", nodo=nid))
            continue
        por_id[nid] = n

    salen: dict[str, list[dict]] = defaultdict(list)
    entran: dict[str, list[dict]] = defaultdict(list)
    ids_con: set[str] = set()
    for c in conexiones:
        cid = c.get("id") or f"{c.get('de')}->{c.get('a')}"
        if cid in ids_con:
            probs.append(_p("ID_DUPLICADO", f"Hay dos conexiones con el id «{cid}».", conexion=cid))
            continue
        ids_con.add(cid)
        if c.get("de") not in por_id or c.get("a") not in por_id:
            probs.append(_p("CONEXION_ROTA", "Una conexión apunta a un nodo que no existe.", conexion=cid))
            continue
        if c["de"] == c["a"]:
            probs.append(_p("CONEXION_A_SI_MISMO", "Un nodo no puede conectarse consigo mismo.", conexion=cid,
                            nodo=c["de"]))
            continue
        c = {**c, "id": cid}
        salen[c["de"]].append(c)
        entran[c["a"]].append(c)

    inicios = [n for n in por_id.values() if n["tipo"] == "inicio"]
    fines = [n for n in por_id.values() if n["tipo"] == "fin"]
    if len(inicios) != 1:
        probs.append(_p("INICIO_UNICO", "Tiene que haber exactamente un nodo Inicio "
                                        f"(hay {len(inicios)})."))
    if not fines:
        probs.append(_p("FIN_REQUERIDO", "Tiene que haber al menos un nodo Fin."))

    # Reglas por tipo de nodo
    for nid, n in por_id.items():
        out = salen.get(nid, [])
        tipo = n["tipo"]
        if len((n.get("nombre") or "")) > 80:
            probs.append(_p("NOMBRE_LARGO", "El nombre no puede pasar de 80 caracteres.", nodo=nid))
        if tipo == "inicio":
            if len(out) != 1:
                probs.append(_p("SALIDAS_INICIO", "El Inicio tiene que tener exactamente una salida.", nodo=nid))
        elif tipo == "fin":
            if out:
                probs.append(_p("FIN_CON_SALIDA", "Un Fin no puede tener salidas.", nodo=nid))
            if n.get("resultado") not in RESULTADOS:
                probs.append(_p("FIN_SIN_RESULTADO", f"«{_nombre(n)}»: elegí si termina Aprobado o Rechazado.",
                                nodo=nid))
        elif tipo == "notificacion":
            if len(out) != 1:
                probs.append(_p("SALIDAS_NOTIFICACION", f"«{_nombre(n)}»: una notificación tiene una sola salida.",
                                nodo=nid))
            dest = n.get("destinatarios") or []
            if not dest:
                probs.append(_p("NOTIFICACION_SIN_DESTINO", f"«{_nombre(n)}»: elegí a quién se avisa.", nodo=nid))
            for d in dest:
                if d.get("tipo") not in TIPOS_DESTINATARIO or (d.get("tipo") != "iniciador"
                                                                 and not str(d.get("valor") or "").strip()):
                    probs.append(_p("DESTINATARIO_INVALIDO", f"«{_nombre(n)}»: hay un destinatario incompleto.",
                                    nodo=nid))
                    break
        elif tipo == "aprobacion":
            probs += _validar_aprobacion(n, out)
        elif tipo == "decision":
            probs += _validar_decision(n, out, variables)
        # Las salidas etiquetadas sólo tienen sentido desde una aprobación; condiciones, desde una decisión.
        for c in out:
            if c.get("salida") and tipo != "aprobacion":
                probs.append(_p("SALIDA_FUERA_DE_APROBACION", "Sólo una aprobación tiene salidas aprobado/rechazado.",
                                conexion=c["id"], nodo=nid))
            if (c.get("condicion") or c.get("defecto")) and tipo != "decision":
                probs.append(_p("CONDICION_FUERA_DE_DECISION", "Sólo una decisión lleva condiciones.",
                                conexion=c["id"], nodo=nid))

    # Alcanzables desde el Inicio y con camino a algún Fin
    if len(inicios) == 1:
        alc = _bfs([inicios[0]["id"]], lambda x: [c["a"] for c in salen.get(x, [])])
        for nid, n in por_id.items():
            if nid not in alc:
                probs.append(_p("HUERFANO", f"«{_nombre(n)}» no se alcanza desde el Inicio.", nodo=nid))
    if fines:
        llega = _bfs([f["id"] for f in fines], lambda x: [c["de"] for c in entran.get(x, [])])
        for nid, n in por_id.items():
            if nid not in llega:
                probs.append(_p("SIN_CAMINO_A_FIN", f"Desde «{_nombre(n)}» no se llega a ningún Fin.", nodo=nid))

    # Un ciclo tiene que pasar por una persona (aprobación): si no, daría vueltas solo para siempre.
    automaticos = {nid for nid, n in por_id.items() if n["tipo"] != "aprobacion"}
    for comp in _componentes_con_ciclo(automaticos, salen):
        probs.append(_p("CICLO_SIN_APROBACION", "Hay un ciclo que no pasa por ninguna aprobación: "
                        + ", ".join(sorted(_nombre(por_id[x]) for x in comp)) + ".", nodo=sorted(comp)[0]))
    return probs


def _validar_aprobacion(n: dict, out: list[dict]) -> list[dict]:
    probs, nid = [], n["id"]
    asignar = n.get("asignar") or {}
    if asignar.get("tipo") == "rol":
        if asignar.get("valor") not in ROLES:
            probs.append(_p("ROL_INVALIDO", f"«{_nombre(n)}»: rol inválido ({asignar.get('valor')!r}).", nodo=nid))
    elif asignar.get("tipo") == "grupo":
        if not str(asignar.get("valor") or "").strip():
            probs.append(_p("GRUPO_VACIO", f"«{_nombre(n)}»: elegí el grupo que aprueba.", nodo=nid))
    else:
        probs.append(_p("SIN_ASIGNACION", f"«{_nombre(n)}»: elegí quién aprueba (rol o grupo).", nodo=nid))
    inc, exc = set(n.get("incluir") or []), set(n.get("excluir") or [])
    if inc & exc:
        probs.append(_p("USUARIO_INCLUIDO_Y_EXCLUIDO", f"«{_nombre(n)}»: {', '.join(sorted(inc & exc))} figura "
                        "como incluido y excluido a la vez.", nodo=nid))
    salidas = [c.get("salida") for c in out]
    for s in SALIDAS_APROBACION:
        if salidas.count(s) != 1:
            probs.append(_p("SALIDAS_APROBACION", f"«{_nombre(n)}»: tiene que tener una salida «{s}».", nodo=nid))
    if any(s not in SALIDAS_APROBACION for s in salidas):
        probs.append(_p("SALIDAS_APROBACION", f"«{_nombre(n)}»: cada salida tiene que ser «aprobado» o «rechazado».",
                        nodo=nid))
    if not n.get("cuatroOjos", True):
        probs.append(_p("SIN_CUATRO_OJOS", f"«{_nombre(n)}»: sin cuatro-ojos, quien envió puede aprobar.",
                        nodo=nid, nivel="aviso"))
    return probs


def _validar_decision(n: dict, out: list[dict], variables: dict) -> list[dict]:
    probs, nid = [], n["id"]
    if len(out) < 2:
        probs.append(_p("SALIDAS_DECISION", f"«{_nombre(n)}»: una decisión necesita al menos dos salidas.", nodo=nid))
    defectos = [c for c in out if c.get("defecto")]
    if len(defectos) != 1:
        probs.append(_p("DECISION_SIN_DEFECTO", f"«{_nombre(n)}»: tiene que haber exactamente una salida «si no» "
                        "(por defecto).", nodo=nid))
    for c in out:
        if c.get("defecto"):
            continue
        cond = c.get("condicion") or {}
        reglas = cond.get("reglas") or []
        if not reglas:
            probs.append(_p("CONDICION_VACIA", f"«{_nombre(n)}»: una salida no tiene condición.", nodo=nid,
                            conexion=c["id"]))
            continue
        if cond.get("modo", "todas") not in ("todas", "alguna"):
            probs.append(_p("CONDICION_INVALIDA", "Modo de condición inválido.", nodo=nid, conexion=c["id"]))
        for r in reglas:
            msg = _problema_regla(r, variables)
            if msg:
                probs.append(_p("CONDICION_INVALIDA", f"«{_nombre(n)}»: {msg}", nodo=nid, conexion=c["id"]))
    return probs


def _problema_regla(r: dict, variables: dict) -> str | None:
    var = variables.get(r.get("variable"))
    if not var:
        return f"la variable «{r.get('variable')}» no existe en este proceso."
    tipo = var.get("tipo")
    if r.get("op") not in OPERADORES.get(tipo, ()):
        return f"el operador «{r.get('op')}» no sirve para «{var.get('nombre', r.get('variable'))}»."
    v = r.get("valor")
    if tipo == "numero" and (isinstance(v, bool) or not isinstance(v, (int, float))):
        return f"«{var.get('nombre')}» se compara con un número."
    if tipo == "booleano" and not isinstance(v, bool):
        return f"«{var.get('nombre')}» se compara con sí/no."
    if tipo == "opcion":
        vals = v if r.get("op") == "en" else [v]
        if not isinstance(vals, list) or not vals or any(x not in var.get("opciones", []) for x in vals):
            return f"valor fuera de las opciones de «{var.get('nombre')}»."
    if tipo == "texto" and not str(v or "").strip():
        return f"falta el texto a comparar en «{var.get('nombre')}»."
    return None


def _bfs(inicio: list[str], vecinos) -> set[str]:
    vistos, cola = set(inicio), list(inicio)
    while cola:
        for x in vecinos(cola.pop()):
            if x not in vistos:
                vistos.add(x)
                cola.append(x)
    return vistos


def _componentes_con_ciclo(nodos: set[str], salen: dict[str, list[dict]]) -> list[set[str]]:
    """Componentes fuertemente conexas (Tarjan iterativo) del subgrafo inducido por `nodos` que tienen
    un ciclo (más de un nodo: los lazos a sí mismo ya se rechazan antes)."""
    indice, bajo, pila, en_pila, res, i = {}, {}, [], set(), [], [0]
    for raiz in sorted(nodos):
        if raiz in indice:
            continue
        trabajo = [(raiz, iter([c["a"] for c in salen.get(raiz, []) if c["a"] in nodos]))]
        indice[raiz] = bajo[raiz] = i[0]; i[0] += 1; pila.append(raiz); en_pila.add(raiz)
        while trabajo:
            v, it = trabajo[-1]
            avanzo = False
            for w in it:
                if w not in indice:
                    indice[w] = bajo[w] = i[0]; i[0] += 1; pila.append(w); en_pila.add(w)
                    trabajo.append((w, iter([c["a"] for c in salen.get(w, []) if c["a"] in nodos])))
                    avanzo = True
                    break
                if w in en_pila:
                    bajo[v] = min(bajo[v], indice[w])
            if avanzo:
                continue
            trabajo.pop()
            if trabajo:
                bajo[trabajo[-1][0]] = min(bajo[trabajo[-1][0]], bajo[v])
            if bajo[v] == indice[v]:
                comp = set()
                while True:
                    w = pila.pop(); en_pila.discard(w); comp.add(w)
                    if w == v:
                        break
                if len(comp) > 1:
                    res.append(comp)
    return res


def errores(problemas: list[dict]) -> list[dict]:
    return [p for p in problemas if p["nivel"] == "error"]


# ── Compatibilidad con el motor actual (Créditos y Tesorería ejecutan cadenas en serie) ─────────
def proyectar(grafo: dict) -> tuple[list[dict] | None, list[str]]:
    """Si el grafo es una cadena en serie que el motor actual sabe ejecutar, devuelve sus niveles en el
    formato de `workflow_niveles` ([{orden, nombre, rol, cuatroOjos, usuarios:[{username, modo}]}]) y [].
    Si no, (None, motivos). Cadena = Inicio → Aprobación 1 → … → Aprobación N → Fin(APROBADO), donde cada
    «rechazado» vuelve al Inicio o va a un Fin(RECHAZADO), sólo con roles (no grupos) y sin otros nodos."""
    motivos: list[str] = []
    nodos = {n["id"]: n for n in grafo.get("nodos") or [] if n.get("id")}
    salen: dict[str, list[dict]] = defaultdict(list)
    for c in grafo.get("conexiones") or []:
        salen[c.get("de")].append(c)
    for n in nodos.values():
        if n.get("tipo") == "decision":
            motivos.append(f"«{_nombre(n)}» es una decisión: el motor actual sólo ejecuta aprobaciones en serie.")
        elif n.get("tipo") == "notificacion":
            motivos.append(f"«{_nombre(n)}» es una notificación: el motor actual todavía no manda avisos.")
        elif n.get("tipo") == "aprobacion" and (n.get("asignar") or {}).get("tipo") != "rol":
            motivos.append(f"«{_nombre(n)}» la aprueba un grupo: el motor actual sólo entiende los roles "
                           "APROBAR y SUPERVISAR.")
    if motivos:
        return None, motivos
    inicios = [n for n in nodos.values() if n.get("tipo") == "inicio"]
    if len(inicios) != 1:
        return None, ["Falta un Inicio único."]
    inicio = inicios[0]["id"]
    niveles, visitados, actual = [], {inicio}, (salen.get(inicio) or [{}])[0].get("a")
    while True:
        n = nodos.get(actual)
        if n is None:
            return None, ["La cadena se corta: hay una conexión que no lleva a ningún nodo."]
        if actual in visitados:
            return None, ["La cadena vuelve sobre sí misma por «aprobado»."]
        visitados.add(actual)
        if n["tipo"] == "fin":
            if n.get("resultado") != "APROBADO":
                return None, ["La cadena de «aprobado» tiene que terminar en un Fin Aprobado."]
            break
        out = {c.get("salida"): c.get("a") for c in salen.get(actual, [])}
        rech = nodos.get(out.get("rechazado")) or {}
        if not (out.get("rechazado") == inicio or (rech.get("tipo") == "fin" and rech.get("resultado") == "RECHAZADO")):
            return None, [f"«{_nombre(n)}»: al rechazar tiene que volver al Inicio o terminar Rechazado."]
        if out.get("rechazado") != inicio:
            visitados.add(out["rechazado"])
        usuarios = ([{"username": u, "modo": "INCLUIR"} for u in n.get("incluir") or []]
                    + [{"username": u, "modo": "EXCLUIR"} for u in n.get("excluir") or []])
        niveles.append({"orden": len(niveles) + 1, "nombre": _nombre(n)[:60], "rol": n["asignar"]["valor"],
                        "cuatroOjos": bool(n.get("cuatroOjos", True)),
                        "usuarios": sorted(usuarios, key=lambda u: u["username"])})
        actual = out.get("aprobado")
    sobran = [nid for nid in nodos if nid not in visitados]
    if sobran:
        return None, ["Hay nodos fuera de la cadena: " + ", ".join(_nombre(nodos[x]) for x in sobran) + "."]
    if not niveles:
        return None, ["Tiene que haber al menos una aprobación (para no exigir aprobación, deshabilitá el proceso)."]
    return niveles, []


# ── Conversión desde una regla vieja (migración a la versión 1) ──────────────────────────────────
def grafo_desde_niveles(niveles: list[dict]) -> tuple[dict, dict]:
    """Regla en serie (formato `serial_regla()["niveles"]`) → (grafo, layout). Rechazar vuelve al Inicio,
    que es lo que hace hoy el motor (reinicia la cadena)."""
    nodos = [{"id": "inicio", "tipo": "inicio", "nombre": "Inicio"}]
    conexiones = []
    layout = {"inicio": {"x": 0, "y": 0}}
    previo = "inicio"
    orden = sorted(niveles, key=lambda x: x["orden"])
    for i, nv in enumerate(orden, start=1):
        nid = f"ap{i}"
        us = nv.get("usuarios") or []
        nodos.append({"id": nid, "tipo": "aprobacion", "nombre": nv.get("nombre") or "Aprobación",
                      "asignar": {"tipo": "rol", "valor": (nv.get("rol") or "APROBAR").upper()},
                      "cuatroOjos": bool(nv.get("cuatroOjos", True)),
                      "incluir": sorted(u["username"] for u in us if u.get("modo") == "INCLUIR"),
                      "excluir": sorted(u["username"] for u in us if u.get("modo") == "EXCLUIR")})
        layout[nid] = {"x": 0, "y": 140 * i}
        conexiones.append({"id": f"c{len(conexiones) + 1}", "de": previo, "a": nid,
                           **({"salida": "aprobado"} if previo != "inicio" else {})})
        conexiones.append({"id": f"c{len(conexiones) + 1}", "de": nid, "a": "inicio", "salida": "rechazado"})
        previo = nid
    nodos.append({"id": "fin", "tipo": "fin", "nombre": "Aprobado", "resultado": "APROBADO"})
    layout["fin"] = {"x": 0, "y": 140 * (len(orden) + 1)}
    conexiones.append({"id": f"c{len(conexiones) + 1}", "de": previo, "a": "fin",
                       **({"salida": "aprobado"} if previo != "inicio" else {})})
    return {"schema": SCHEMA, "nodos": nodos, "conexiones": conexiones}, layout


# ── Huella y comparación ─────────────────────────────────────────────────────────────────────────
def huella(grafo: dict) -> str:
    """Hash estable del contenido semántico (independiente del orden de nodos/conexiones)."""
    canon = {"schema": grafo.get("schema", SCHEMA),
             "nodos": sorted(grafo.get("nodos") or [], key=lambda n: str(n.get("id"))),
             "conexiones": sorted(({k: v for k, v in c.items() if k != "id"} for c in grafo.get("conexiones") or []),
                                  key=lambda c: json.dumps(c, sort_keys=True))}
    return hashlib.sha256(json.dumps(canon, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


_CAMPOS_LEGIBLES = {"nombre": "nombre", "asignar": "quién aprueba", "cuatroOjos": "cuatro-ojos",
                    "incluir": "usuarios incluidos", "excluir": "usuarios excluidos", "resultado": "resultado",
                    "destinatarios": "destinatarios", "mensaje": "mensaje"}


def _clave_conexion(c: dict) -> tuple:
    return (c.get("de"), c.get("a"), c.get("salida") or "", bool(c.get("defecto")))


def comparar(a: dict, b: dict) -> dict:
    """Diferencias de `a` (anterior) a `b` (nueva): nodos agregados/quitados/modificados y conexiones
    agregadas/quitadas, más un resumen en castellano."""
    na = {n["id"]: n for n in a.get("nodos") or []}
    nb = {n["id"]: n for n in b.get("nodos") or []}
    agregados = [nid for nid in nb if nid not in na]
    quitados = [nid for nid in na if nid not in nb]
    modificados = []
    for nid in nb:
        if nid in na and na[nid] != nb[nid]:
            campos = sorted({k for k in set(na[nid]) | set(nb[nid]) if na[nid].get(k) != nb[nid].get(k)})
            modificados.append({"id": nid, "campos": campos})
    ca = {_clave_conexion(c): c for c in a.get("conexiones") or []}
    cb = {_clave_conexion(c): c for c in b.get("conexiones") or []}
    con_agregadas = [cb[k] for k in cb if k not in ca]
    con_quitadas = [ca[k] for k in ca if k not in cb]
    con_modificadas = [cb[k] for k in cb if k in ca and (ca[k].get("condicion") != cb[k].get("condicion"))]

    resumen = []
    for nid in agregados:
        resumen.append(f"+ {nb[nid]['tipo']} «{_nombre(nb[nid])}»")
    for nid in quitados:
        resumen.append(f"− {na[nid]['tipo']} «{_nombre(na[nid])}»")
    for m in modificados:
        campos = ", ".join(_CAMPOS_LEGIBLES.get(c, c) for c in m["campos"])
        resumen.append(f"~ «{_nombre(nb[m['id']])}»: cambia {campos}")
    if con_agregadas or con_quitadas or con_modificadas:
        resumen.append(f"conexiones: +{len(con_agregadas)} −{len(con_quitadas)} ~{len(con_modificadas)}")
    return {"nodos": {"agregados": agregados, "quitados": quitados, "modificados": modificados},
            "conexiones": {"agregadas": con_agregadas, "quitadas": con_quitadas, "modificadas": con_modificadas},
            "resumen": resumen, "iguales": not resumen}


# ── Normalización (lo que se guarda) ─────────────────────────────────────────────────────────────
_CLAVES_NODO = {"id", "tipo", "nombre", "asignar", "incluir", "excluir", "cuatroOjos", "destinatarios",
                "mensaje", "resultado"}
_CLAVES_CONEXION = {"id", "de", "a", "salida", "condicion", "defecto", "etiqueta"}


def _texto(v, largo: int) -> str:
    return str(v if v is not None else "").strip()[:largo]


def normalizar(grafo: dict) -> dict:
    """Se queda sólo con las claves conocidas y recorta textos: lo que llega del editor se guarda limpio
    (la validación semántica es aparte y no bloquea el guardado del borrador)."""
    if not isinstance(grafo, dict):
        raise ValueError("El grafo tiene que ser un objeto.")
    nodos_in, con_in = grafo.get("nodos") or [], grafo.get("conexiones") or []
    if not isinstance(nodos_in, list) or not isinstance(con_in, list):
        raise ValueError("`nodos` y `conexiones` tienen que ser listas.")
    if len(nodos_in) > MAX_NODOS or len(con_in) > MAX_NODOS * 4:
        raise ValueError(f"El workflow no puede tener más de {MAX_NODOS} nodos.")
    nodos = []
    for n in nodos_in:
        if not isinstance(n, dict):
            raise ValueError("Cada nodo tiene que ser un objeto.")
        m = {k: v for k, v in n.items() if k in _CLAVES_NODO}
        m["id"], m["tipo"] = _texto(m.get("id"), 40), _texto(m.get("tipo"), 20)
        if "nombre" in m:
            m["nombre"] = _texto(m["nombre"], 120)   # >80 lo marca la validación, no se corta en silencio
        if "mensaje" in m:
            m["mensaje"] = _texto(m["mensaje"], 500)
        if "resultado" in m:
            m["resultado"] = _texto(m["resultado"], 10)
        for k in ("incluir", "excluir"):
            if k in m:
                m[k] = sorted({_texto(u, 60) for u in (m[k] or []) if _texto(u, 60)})
        if "asignar" in m:
            a = m["asignar"] if isinstance(m["asignar"], dict) else {}
            m["asignar"] = {"tipo": _texto(a.get("tipo"), 10), "valor": _texto(a.get("valor"), 80),
                            **({"id": a["id"]} if isinstance(a.get("id"), int) and not isinstance(a.get("id"), bool)
                               else {})}
        if "destinatarios" in m:
            m["destinatarios"] = [{"tipo": _texto(d.get("tipo"), 10), "valor": _texto(d.get("valor"), 80)}
                                  for d in (m["destinatarios"] or []) if isinstance(d, dict)][:20]
        if "cuatroOjos" in m:
            m["cuatroOjos"] = bool(m["cuatroOjos"])
        nodos.append(m)
    conexiones = []
    for c in con_in:
        if not isinstance(c, dict):
            raise ValueError("Cada conexión tiene que ser un objeto.")
        m = {k: v for k, v in c.items() if k in _CLAVES_CONEXION and v not in (None, "", False)}
        for k in ("id", "de", "a"):
            m[k] = _texto(m.get(k), 40)
        if "etiqueta" in m:
            m["etiqueta"] = _texto(m["etiqueta"], 40)
        if "salida" in m:
            m["salida"] = _texto(m["salida"], 10)
        if "defecto" in m:
            m["defecto"] = True
            m.pop("condicion", None)
        if "condicion" in m:
            cond = m["condicion"] if isinstance(m["condicion"], dict) else {}
            reglas = [{"variable": _texto(r.get("variable"), 40), "op": _texto(r.get("op"), 10),
                       "valor": r.get("valor")} for r in (cond.get("reglas") or []) if isinstance(r, dict)][:10]
            m["condicion"] = {"modo": _texto(cond.get("modo") or "todas", 10), "reglas": reglas}
        conexiones.append(m)
    return {"schema": SCHEMA, "nodos": nodos, "conexiones": conexiones}


def normalizar_layout(layout, grafo: dict) -> dict:
    ids = {n["id"] for n in grafo.get("nodos") or []}
    out = {}
    if not isinstance(layout, dict):
        return out
    for k, v in layout.items():
        if k in ids and isinstance(v, dict):
            try:
                out[k] = {"x": round(float(v.get("x", 0)), 1), "y": round(float(v.get("y", 0)), 1)}
            except (TypeError, ValueError):
                continue
    return out
