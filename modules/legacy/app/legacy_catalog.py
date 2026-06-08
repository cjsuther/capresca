"""
Catálogo de la topología del sistema legacy Visual FoxPro 9.

Define las bases de datos lógicas del legacy (subdirectorios del share
\\192.168.0.7\\agjs), las tablas DBF que contiene cada una, y los metadatos
necesarios para localizarlas y sincronizarlas.

Es la fuente única de verdad para:
  - resolver la ruta física de una tabla (dbf_reader / dbf_writer)
  - mapear tabla -> base de datos lógica (interaction_log, frontend)
  - saber qué tablas son sincronizables y cuáles son de solo lectura estricta
"""

# database lógica -> { subdir, dbc, tables: {nombre_tabla: archivo.dbf} }
LEGACY_CATALOG = {
    "caja": {
        "subdir": "caja",
        "dbc": "agjscaja.dbc",
        "tables": {
            "cajaliq": "cajaliq.dbf",
            "cajapagos": "cajapagos.dbf",
            "cajaforpag": "cajaforpag.dbf",
            "cajacreseg": "cajacreseg.dbf",
        },
    },
    "juegos": {
        "subdir": "juegos",
        "dbc": "agjsjuegos.dbc",
        "tables": {
            "maejuegos": "maejuegos.dbf",
            "maeagencias": "maeagencias.dbf",
        },
    },
    "creditos": {
        "subdir": "creditos",
        "dbc": "agjscreditos.dbc",
        "tables": {
            "maeclientes": "maeclientes.dbf",
            "solicitud": "solicitud.dbf",
            "hisolicitud": "hisolicitud.dbf",
            "maecuotas": "maecuotas.dbf",
            "himaecuotas": "himaecuotas.dbf",
            "lineacred": "lineacred.dbf",
        },
    },
    "general": {
        "subdir": "general",
        "dbc": None,  # tablas libres
        "tables": {
            "maestrodio": "maestrodio.dbf",
            "organismos": "organismos.dbf",
        },
    },
    "contabilidad": {
        "subdir": "contabilidad",
        "dbc": None,
        "tables": {
            # Tablas consolidadas: se vacían con ZAP y exigen acceso EXCLUSIVO.
            # SOLO LECTURA segura entre cierres; jamás escribir desde este módulo.
            "solble": "solble.dbf",
            "ctable": "ctable.dbf",
        },
    },
}

# Bases de datos lógicas válidas (para validación de filtros del frontend)
DATABASES = tuple(LEGACY_CATALOG.keys())

# tabla -> database lógica
TABLE_DATABASE = {
    table: db
    for db, meta in LEGACY_CATALOG.items()
    for table in meta["tables"]
}

# Tablas que NUNCA deben escribirse desde este módulo (consolidadas/exclusivas)
READ_ONLY_TABLES = frozenset({"solble", "ctable"})


def database_of(table_name: str) -> str | None:
    """Devuelve la base de datos lógica a la que pertenece una tabla."""
    return TABLE_DATABASE.get(table_name)


def relative_path(table_name: str) -> str | None:
    """Ruta relativa (subdir/archivo.dbf) de una tabla dentro del share."""
    db = TABLE_DATABASE.get(table_name)
    if db is None:
        return None
    meta = LEGACY_CATALOG[db]
    return f"{meta['subdir']}/{meta['tables'][table_name]}"
