"""Registro declarativo de migradores DBF → modelo actual.

Cada `Migrador` documenta: el programa VFP de origen, el/los DBF, la tabla
destino, las conversiones de campos y la función loader. El registro permite
mostrar el catálogo en la UI y **re-ejecutar** cada migración cuando se
actualicen los DBFs (con `reset=True` se trunca la tabla y se vuelve a cargar).

Pensado para que la app pueda re-migrar contra datos reales siempre que el
sistema legacy exporte nuevos .dbf.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Callable

from sqlalchemy import text

from app.core.database import engine, SessionLocal
from app.etl import (cargar_maestros, cargar_creditos, cargar_ctacte,
                     cargar_solicitudes, cargar_seguros, cargar_polizas,
                     cargar_juegos, cargar_hisliq, cargar_tramites,
                     cargar_despacho, cargar_egresos_ledger, cargar_cheques,
                     cargar_contable, cargar_auditoria, cargar_jubilados,
                     cargar_ccseguros, cargar_asientos_pd, cargar_contab_caja)

# Directorio donde el contenedor monta el backup del sistema legacy.
BASES = os.getenv("BASES_DIR", "/bases")


@dataclass
class Migrador:
    clave: str
    nombre: str
    modulo: str
    dbf: str                       # ruta relativa dentro de BASES (o carpeta)
    programa: str                  # programa/form VFP de origen
    tabla: str                     # tabla destino principal
    loader: Callable[[str], None]  # función cargar(bases)
    conversiones: list[tuple[str, str, str]]   # (campo_dbf, campo_modelo, tipo/nota)
    tablas: list[str] = field(default_factory=list)  # tablas a truncar en reset (hijas primero)
    esperado: int | None = None    # registros esperados (informativo)

    def __post_init__(self):
        if not self.tablas:
            self.tablas = [self.tabla]


# Orden de carga (padres → hijos) para "ejecutar todo".
REGISTRO: list[Migrador] = [
    Migrador(
        clave="maestros", nombre="Organismos, líneas y clientes/agentes", modulo="Créditos",
        dbf="General/organismos.dbf · Creditos/lineas.dbf · maeclientes",
        programa="frm905250000AB (organismos) · líneas de crédito · maeclientes/maestrodio",
        tabla="clientes", tablas=["clientes", "lineas_credito", "organismos"], esperado=78055,
        loader=cargar_maestros.cargar,
        conversiones=[
            ("CIDCLIENTE", "id_cliente", "int"), ("CCUIL", "cuil", "str(11)"),
            ("EDNI", "dni", "str(9)"), ("CAPENOM", "apellido_nombre", "str(80)"),
            ("NSUELDO", "sueldo", "Numeric"), ("CCBUCTA", "cbu", "str"),
            ("ORGANO", "organismo_id", "int"), ("LDEBAUTO", "debito_automatico", "bool"),
            ("NO_LINEA", "id (línea)", "int"), ("TNA", "tna", "Numeric"),
            ("POR_AFECTA", "por_afecta", "Numeric"), ("DENOMINACI", "nombre (organismo/línea)", "str"),
        ]),
    Migrador(
        clave="creditos", nombre="Créditos, cuotas y turnos", modulo="Créditos",
        dbf="Creditos/ (maecred, maecuotas, turnos)",
        programa="agjscreditos!maecred / maecuotas (otorgamiento y plan de cuotas)",
        tabla="creditos", tablas=["cuotas", "turnos_credito", "creditos"], esperado=None,
        loader=cargar_creditos.cargar,
        conversiones=[
            ("NO_CREDITO", "id", "int"), ("CIDCLI", "cliente_id", "FK cliente"),
            ("NLINEA", "linea_id", "FK línea"), ("CAPITAL", "capital", "Numeric"),
            ("SDO_CAP", "saldo_capital", "Numeric"), ("CESTADO", "estado", "A/C/B"),
            ("NO_CUOTA", "numero (cuota)", "int"), ("FECHA_VTO", "fecha_vencimiento", "date"),
            ("TOTAL", "total (cuota)", "Numeric"), ("ESTADO", "estado (cuota) P=pagada", "str"),
            ("NTURNO", "numero (turno)", "int"), ("PERIODO", "periodo", "YYYYMM"),
        ]),
    Migrador(
        clave="ctacte", nombre="Cuenta corriente de créditos", modulo="Créditos",
        dbf="Creditos/ctacte.dbf", programa="agjscreditos!ctacte (movimientos de cta. cte.)",
        tabla="movimientos_cta", tablas=["movimientos_cta"], esperado=None,
        loader=cargar_ctacte.cargar,
        conversiones=[
            ("NNO_CREDIT", "credito_id", "FK crédito"), ("NNO_CUOTA", "no_cuota", "int"),
            ("TFECHA", "fecha", "date"), ("NCAPITAL", "capital", "Numeric"),
            ("NINTERES", "interes", "Numeric"), ("NINT_PUNI", "interes_punitorio", "Numeric"),
            ("NIVA", "iva", "Numeric"), ("NNO_RECIBO", "no_recibo", "int"),
        ]),
    Migrador(
        clave="solicitudes", nombre="Solicitudes de crédito (anexo)", modulo="Créditos",
        dbf="Creditos/solicitud.dbf", programa="120100000anexo_res_dis (anexo de resolución 12010)",
        tabla="solicitudes_credito", tablas=["solicitudes_credito"], esperado=None,
        loader=cargar_solicitudes.cargar,
        conversiones=[
            ("NO_SOLICIT", "id", "int"), ("SO_CUIL", "cuil", "str(11)"),
            ("SO_APENOM", "apellido_nombre", "str(80)"), ("SO_DNI", "dni", "str(9)"),
            ("MONTOSOL", "montosol", "Numeric"), ("NO_CREDPP", "no_credpp", "int"),
            ("NO_RESOL", "no_resol", "int"), ("FECHA_SOLI", "fecha_soli", "date"),
        ]),
    Migrador(
        clave="seguros", nombre="Titulares, seguro del agente y regímenes", modulo="Seguros",
        dbf="Seguros/ (titulares, segurosap, agjsseguros)",
        programa="frm705050000MA (titulares Ley 5182) · segurosap · agjsseguros (regímenes)",
        tabla="titulares_seguro",
        tablas=["beneficiarios", "regimenes_especiales", "seguros_agente", "titulares_seguro"],
        esperado=122784, loader=cargar_seguros.cargar,
        conversiones=[
            ("CUIL", "cuil", "str(11)"), ("APENOM/TITULAR", "apellido_nombre", "str(80)"),
            ("TIPO_TITUL", "tipo_titular", "str"), ("ORGANO", "organo", "int"),
            ("NO_AGENTE", "no_agente", "int"), ("SEG_OBLIGA", "seg_obligatorio", "Numeric"),
            ("SEG_SEPELI", "seg_sepelio", "Numeric"), ("SEG_ADICIO", "seg_adicional", "Numeric"),
            ("PERIODO", "periodo", "MMYYYY"),
        ]),
    Migrador(
        clave="polizas", nombre="Pólizas de seguro de vida (por agente)", modulo="Seguros",
        dbf="Seguros/seguros.DBF", programa="Seguro de vida colectivo por agente (paraseguros define tipos)",
        tabla="polizas_agente", tablas=["polizas_agente"], esperado=207498,
        loader=cargar_polizas.cargar,
        conversiones=[
            ("CODIGO", "codigo", "tipo (1 Subs.Familia · 2 Sepelio · 3 Vida oblig. · 4 Incap. · 5 Adic.)"),
            ("NO_POLIZA", "no_poliza", "int"), ("CUIL", "cuil", "str(11)"),
            ("NO_AGENTE", "no_agente", "int"), ("ESTADO", "estado", "A=activa"),
            ("BAJA", "baja", "bool"), ("CANTIDAD", "cantidad", "int"),
            ("FECHA_ALTA", "fecha_alta", "date"),
        ]),
    Migrador(
        clave="ccseguros", nombre="Cuenta corriente de seguros (por agente)", modulo="Seguros",
        dbf="Seguros/ccseguros.dbf", programa="cta. cte. de seguros del agente (cargos por período)",
        tabla="ctacte_seguros", tablas=["ctacte_seguros"], esperado=180501,
        loader=cargar_ccseguros.cargar,
        conversiones=[
            ("CUIL", "cuil", "str(11)"), ("NO_AGENTE", "no_agente", "int"),
            ("SEXO", "sexo", "str(1)"), ("PERIODO", "periodo", "MMYYYY"),
            ("SEGURO", "seguro", "tipo de seguro"), ("IMPORTE", "importe", "Numeric"),
            ("FECHA_ALTA", "fecha_alta", "date"),
        ]),
    Migrador(
        clave="juegos", nombre="Juegos, agencias, sorteos y liquidaciones", modulo="Juegos",
        dbf="Caja/ (cajaliq, cajapagos, cajacreseg) · maejuegos · maeagencias",
        programa="aplicaj (aplicativo de caja) · maejuegos · maeagencias",
        tabla="liquidaciones_agencia",
        tablas=["caja_creseg", "caja_pagos_agencia", "liquidaciones_agencia", "sorteos_juego", "agencias_juego", "juegos"],
        esperado=60000, loader=cargar_juegos.cargar,
        conversiones=[
            ("COD_AGENCI", "cod_agencia", "int"), ("COD_JUEGO", "cod_juego", "int"),
            ("NO_SORTEO", "no_sorteo", "int"), ("RECAUDACIO", "recaudacion", "Numeric"),
            ("ING_BRUTOS", "ing_brutos", "Numeric"), ("FDO_GTIA", "fdo_gtia", "Numeric"),
            ("TOTAL_GRAL", "total_gral", "Numeric"), ("FECHA_VTO", "fecha_vto", "date"),
            ("PAGADO", "pagado", "bool"), ("BONOS/PESOS/COBRADO", "cajapagos", "pagos de agencia"),
        ]),
    Migrador(
        clave="hisliq", nombre="Liquidaciones de agencia históricas", modulo="Juegos",
        dbf="Juegos/jghisliq.DBF", programa="frm425150000HI (pasa liquidaciones a histórico)",
        tabla="liquidaciones_historicas", tablas=["liquidaciones_historicas"], esperado=273589,
        loader=cargar_hisliq.cargar,
        conversiones=[
            ("COD_AGENCI", "cod_agencia", "int"), ("NO_AGENCIA", "no_agencia", "int"),
            ("COD_JUEGO", "cod_juego", "int"), ("FECHA", "fecha", "date"),
            ("RECAUDACIO", "recaudacion", "Numeric"), ("FDO_GTIA", "fdo_gtia", "Numeric"),
            ("ING_BRUTOS", "ing_brutos", "Numeric"), ("TOTAL", "total", "Numeric"),
        ]),
    Migrador(
        clave="tramites", nombre="Mesa de entradas: trámites, pases y maestros", modulo="Mesa",
        dbf="Mesa/ (tramites, pases, oficinas, perfiles, proveedores)",
        programa="frm515050000TR (trámites) · pases · maeoficinas · symdeperf · proveedores",
        tabla="tramites",
        tablas=["tramite_pases", "tramites", "tramite_tipos", "oficinas", "perfiles", "proveedores"],
        esperado=None, loader=cargar_tramites.cargar,
        conversiones=[
            ("ID_TRAMITE", "id", "str"), ("ID_LETRA/ID_NRO/ID_ANO", "expediente", "compuesto"),
            ("OFICINA_AC", "oficina_actual", "FK oficina"), ("ESTADO", "estado", "str"),
            ("FECHA_PASE", "fecha_pase", "date"), ("COD_PERFIL", "codigo (perfil)", "str"),
            ("NPROVEEDOR", "id (proveedor)", "int"), ("CRAZONSOC", "razon_social", "str"),
        ]),
    Migrador(
        clave="despacho", nombre="Modelos, resoluciones/disposiciones y beneficiarios", modulo="Despacho",
        dbf="Despacho/rtf.dbf · Despacho/resoluciones.dbf · Despacho/beneficiarios.dbf",
        programa="105050000MODEL (modelos) · resoluciones/disposiciones · beneficiarios",
        tabla="resoluciones",
        tablas=["resolucion_beneficiarios", "resoluciones", "modelos_resolucion"], esperado=53000,
        loader=cargar_despacho.cargar,
        conversiones=[
            ("COD_MOD", "codigo (modelo)", "int"), ("DES_MOD", "descripcion", "str"),
            ("MODELO", "plantilla (memo)", "texto base"),
            ("NRO_RES", "numero (correlativo)", "int"), ("FEC_RES", "fecha", "date"),
            ("NRO_REAL", "numero_real", "int"), ("FEC_REAL", "fecha_real", "date"),
            ("TIPO_RES/DISPOSICIO", "tipo", "RES/DIS"), ("COD_MOT", "motivo_cod", "int"),
            ("IMPORTE", "importe", "Numeric"), ("ID_TRAMITE/ID_LETRA/ID_NRO/ID_ANO", "origen", "str"),
            ("NRO_OP", "nro_op", "int"), ("TEXTO", "texto", "memo"), ("LANULADA", "anulada", "bool"),
            ("TIPO_DOC/NRO_DOC/NOMBRE/TIPO_BENE", "beneficiarios[]", "grilla"),
        ]),
    Migrador(
        clave="egresos", nombre="Ledger de egresos (transacciones)", modulo="Tesorería",
        dbf="Egresos/egresos.dbf", programa="frm815050000buscaegresos (81505)",
        tabla="egresos", tablas=["egresos"], esperado=339903,
        loader=cargar_egresos_ledger.cargar,
        conversiones=[
            ("SUB_TIPO", "sub_tipo", "int"), ("NO_LIQUIDA", "no_liquida", "int"),
            ("NRO_RES", "nro_res", "int"), ("NO_CREDITO", "no_credito", "int"),
            ("APENOM", "apenom", "str(40)"), ("CUIL", "cuil", "str(11)"),
            ("NO_OP", "no_op", "int"), ("TOTAL", "total", "Numeric"),
            ("PAGADO", "pagado", "bool"), ("LANULADA", "anulado", "bool"),
        ]),
    Migrador(
        clave="cheques", nombre="Cheques emitidos", modulo="Tesorería",
        dbf="Egresos/cheques.dbf", programa="frm830400000CH (83040 listado de cheques)",
        tabla="cheques_emitidos", tablas=["cheques_emitidos"], esperado=73276,
        loader=cargar_cheques.cargar,
        conversiones=[
            ("NBANCO", "banco", "int"), ("NCUENTA", "ncuenta", "int"),
            ("CUENTA", "cuenta", "tipo de chequera"), ("NCHEQUE", "ncheque", "int"),
            ("FECHA", "fecha", "date"), ("NIMPORTE", "importe", "Numeric"),
            ("NOP", "nop", "int"), ("NRES", "nres", "int"),
            ("NLIQUI", "nliqui", "int"), ("LANULA", "anulado", "bool"),
        ]),
    Migrador(
        clave="contable", nombre="Libro mayor (asientos)", modulo="Contabilidad",
        dbf="Contabilidad/asientos.dbf", programa="Libro mayor / libro diario contable",
        tabla="movimientos_contables", tablas=["movimientos_contables"], esperado=2009400,
        loader=cargar_contable.cargar,
        conversiones=[
            ("CUENTA", "cuenta", "str"), ("CTAPLAN", "ctaplan", "str"),
            ("FECHA", "fecha", "date"), ("CPERIO", "periodo", "str"),
            ("NORDEN", "norden", "int"), ("NDEBITO", "debito", "Numeric"),
            ("NCREDITO", "credito", "Numeric"), ("CREFERENCI", "referencia", "str"),
        ]),
    Migrador(
        clave="asientos_pd", nombre="Libro diario por partida doble (reconstruido)", modulo="Contabilidad",
        dbf="Contabilidad/asientos.dbf (reconstruido desde el mayor por partida doble)",
        programa="cb-crasientootorga / cb-crasientodevenga (partida doble)",
        tabla="asientos", tablas=["asientos_lineas", "asientos"], esperado=1049890,
        loader=cargar_asientos_pd.cargar,
        conversiones=[
            ("(periodo,fecha,CREFERENCI)", "asientos (cabecera)", "agrupa las piernas del asiento"),
            ("CREFERENCI", "concepto", "referencia del asiento"),
            ("FECHA", "fecha", "date"), ("CTAPLAN", "cuenta_codigo (línea)", "str(12)"),
            ("CUENTA", "cuenta_nombre (línea)", "str(80)"),
            ("NDEBITO", "debe (línea)", "Numeric"), ("NCREDITO", "haber (línea)", "Numeric"),
        ]),
    Migrador(
        clave="crctacte", nombre="Cta. cte. contable de créditos (detalle)", modulo="Contabilidad",
        dbf="Contabilidad/crctacte.dbf", programa="cta. cte. contable de créditos (desglose por cuota)",
        tabla="ctacte_contable_credito", tablas=["ctacte_contable_credito"], esperado=1049892,
        loader=cargar_contab_caja.cargar_crctacte,
        conversiones=[
            ("CUENTA", "cuenta", "cartera"), ("NCREDITO", "no_credito", "int"),
            ("NCUOTA", "no_cuota", "int"), ("FECVTO", "fecha_vto", "date"),
            ("FECHAPAGO", "fecha_pago", "date"), ("NSALDO", "saldo", "Numeric"),
            ("NCAPITAL", "capital", "Numeric"), ("NINTNOR", "int_normal", "Numeric"),
            ("NINTPUN", "int_punit", "Numeric"), ("NGSAS", "gastos", "Numeric"),
            ("LANULADA", "anulada", "bool"),
        ]),
    Migrador(
        clave="contgral", nombre="Contabilidad general (caja/juegos)", modulo="Contabilidad",
        dbf="Contabilidad/contgral.dbf", programa="contabilidad general por asiento (importes por moneda)",
        tabla="contabilidad_general", tablas=["contabilidad_general"], esperado=106557,
        loader=cargar_contab_caja.cargar_contgral,
        conversiones=[
            ("FECHA", "fecha", "date"), ("NAAMM", "periodo", "AAAAMM"),
            ("NASIENTO", "asiento", "int"), ("NRECIBO", "recibo", "int"),
            ("CTIPO", "tipo", "I/E"), ("CDESTINO", "destino", "str"),
            ("CORIGEN", "origen", "str"), ("NTOTPES", "total_pesos", "Numeric"),
            ("NTOTBON", "total_bonos", "Numeric"), ("NTOTLEC", "total_lecop", "Numeric"),
        ]),
    Migrador(
        clave="cj_crsghis", nombre="Crédito/seguro cobrado en caja (histórico)", modulo="Caja",
        dbf="Caja/cj_crsghis.dbf", programa="histórico de crédito/seguro cobrado en caja (cajacreseg)",
        tabla="caja_creseg_historico", tablas=["caja_creseg_historico"], esperado=143722,
        loader=cargar_contab_caja.cargar_crsghis,
        conversiones=[
            ("NO_CREDITO", "no_credito", "int"), ("CUIL", "cuil", "str(11)"),
            ("APENOM", "apellido_nombre", "str(60)"), ("INTERES", "interes", "Numeric"),
            ("NSEG", "seguro", "Numeric"), ("TOTAL_GRAL", "total_gral", "Numeric"),
            ("MONEDA", "moneda", "str"), ("FECHA_PAGO", "fecha_pago", "date"),
            ("NO_RECIBO", "no_recibo", "int"),
        ]),
    Migrador(
        clave="cj_liqhis", nombre="Liquidaciones de agencia (histórico)", modulo="Caja",
        dbf="Caja/cj_liqhis.dbf", programa="histórico de liquidaciones de agencia (cajaliq)",
        tabla="liquidaciones_agencia_hist", tablas=["liquidaciones_agencia_hist"], esperado=1370363,
        loader=cargar_contab_caja.cargar_liqhis,
        conversiones=[
            ("COD_AGENCI", "cod_agencia", "int"), ("COD_JUEGO", "cod_juego", "int"),
            ("NO_SORTEO", "no_sorteo", "int"), ("FECHA_SORT", "fecha_sorteo", "date"),
            ("RECAUDACIO", "recaudacion", "Numeric"), ("FDO_GTIA", "fdo_gtia", "Numeric"),
            ("ING_BRUTOS", "ing_brutos", "Numeric"), ("TOTAL_GRAL", "total_gral", "Numeric"),
            ("PAGADO", "pagado", "bool"), ("LANULA", "anulado", "bool"),
        ]),
    Migrador(
        clave="cj_paghis", nombre="Pagos de agencia (histórico)", modulo="Caja",
        dbf="Caja/cj_paghis.dbf", programa="histórico de pagos de agencia (cajapagos)",
        tabla="caja_pagos_agencia_hist", tablas=["caja_pagos_agencia_hist"], esperado=652538,
        loader=cargar_contab_caja.cargar_paghis,
        conversiones=[
            ("COD_AGENCI", "cod_agencia", "int"), ("FECHA_PAGO", "fecha_pago", "date"),
            ("ORIGEN", "origen", "str"), ("NO_RECIBO", "no_recibo", "int"),
            ("BONOS", "bonos", "Numeric"), ("PESOS", "pesos", "Numeric"),
            ("COBRADO_TO", "cobrado_total", "Numeric"), ("PREMIOS_PE", "premios_pesos", "Numeric"),
            ("CAJERO", "cajero", "str"), ("ANULADO", "anulado", "bool"),
        ]),
    Migrador(
        clave="auditoria", nombre="Log de auditoría (muestra)", modulo="Seguridad",
        dbf="General/auditoria.dbf", programa="rpt106auditoria (log de eventos, 6,5M · muestra 50k)",
        tabla="eventos_auditoria", tablas=["eventos_auditoria"], esperado=50000,
        loader=cargar_auditoria.cargar,
        conversiones=[
            ("HORA_EVENT", "fecha_hora", "datetime"), ("MAQUINA", "maquina", "str(40)"),
            ("USUARIO", "usuario", "str(40)"), ("CSISTEMA", "sistema", "str(20)"),
            ("CPERFIL", "perfil", "str(8)"), ("PROCESO", "proceso", "str(60)"),
            ("OPCION", "opcion", "str(80)"),
        ]),
    Migrador(
        clave="jubilados", nombre="Jubilados / Ley 5094 (marca en créditos)", modulo="Créditos",
        dbf="Creditos/ (jubilados Ley 5094)", programa="frm835050000MO (subsidios jubilados)",
        tabla="creditos", tablas=[], esperado=None,  # actualiza, no trunca
        loader=cargar_jubilados.cargar,
        conversiones=[("(marca de crédito jubilatorio)", "creditos.*", "update in-place")]),
]

REGISTRO_POR_CLAVE = {m.clave: m for m in REGISTRO}

# Tablas del modelo que la app genera (sin origen legacy) o auxiliares, con su
# módulo para el DER. `origen=None` en el esquema significa "no viene de un DBF".
MODULO_EXTRA: dict[str, str] = {
    "asientos": "Contabilidad", "asientos_lineas": "Contabilidad",
    "cuentas_contables": "Contabilidad",
    "recibos": "Caja", "pago_cuotas": "Caja", "pagos_cuota": "Caja",
    "polizas": "Seguros", "companias_seguros": "Seguros",
    "autorizaciones_op": "Tesorería", "ordenes_pago": "Tesorería",
    "chequeras": "Tesorería", "cheques": "Tesorería",
    "requisitos": "Créditos", "solicitudes": "Créditos",
}

# Archivos .dbf reales que lee cada loader (para el inventario por carpeta).
DBFS_USADOS: dict[str, list[str]] = {
    "maestros": ["General/organismos.dbf", "Creditos/lineacred.dbf", "Creditos/maeclientes.dbf"],
    "creditos": ["Creditos/crcliact.dbf", "Creditos/maecuotas.dbf", "Creditos/turnos.dbf"],
    "ctacte": ["Creditos/ctacte.dbf"],
    "solicitudes": ["Creditos/solicitud.dbf"],
    "seguros": ["Seguros/titulares.dbf", "Seguros/segurosap.dbf", "Seguros/excombate.dbf", "Seguros/subsidio.dbf"],
    "polizas": ["Seguros/seguros.DBF"],
    "ccseguros": ["Seguros/ccseguros.dbf"],
    "juegos": ["Caja/agenjuegos.dbf", "Caja/cajaliq.dbf", "Caja/cajapagos.dbf",
               "Caja/cajacreseg.dbf", "Juegos/maejuegos.dbf", "Juegos/maejugadas.dbf"],
    "hisliq": ["Juegos/jghisliq.DBF"],
    "tramites": ["Mesa/maeperfil.dbf", "Mesa/oficinas.dbf", "Mesa/pases.dbf",
                 "Mesa/proveedores.dbf", "Mesa/tipotram.dbf", "Mesa/tramites.dbf"],
    "despacho": ["Despacho/resoluciones.dbf", "Despacho/rtf.dbf", "Despacho/beneficiarios.dbf"],
    "egresos": ["Egresos/egresos.dbf"],
    "cheques": ["Egresos/cheques.dbf"],
    "contable": ["Contabilidad/asientos.dbf"],
    "crctacte": ["Contabilidad/crctacte.dbf"],
    "contgral": ["Contabilidad/contgral.dbf"],
    "cj_crsghis": ["Caja/cj_crsghis.dbf"],
    "cj_liqhis": ["Caja/cj_liqhis.dbf"],
    "cj_paghis": ["Caja/cj_paghis.dbf"],
    "auditoria": ["General/auditoria.dbf"],
    "jubilados": ["Creditos/jub_ctas.dbf", "Creditos/sol_jubi.dbf"],
}


# En qué opciones de menú (pantallas) se usa cada tabla del modelo. Se mantiene a
# mano al cablear cada pantalla. Tablas sin entrada = migradas pero aún sin pantalla.
USOS_MENU: dict[str, list[tuple[str, str]]] = {
    "clientes": [("/clientes/maestro", "Clientes · Maestro (ABM)"),
                 ("/clientes/vision-360", "Clientes · Visión 360°"),
                 ("/creditos/situacion", "Créditos · Situación del cliente")],
    "creditos": [("/creditos/situacion", "Créditos · Situación"),
                 ("/creditos/listado", "Créditos · Listado"),
                 ("/creditos/cuenta-corriente", "Créditos · Cuenta corriente"),
                 ("/clientes/vision-360", "Clientes · Visión 360°"),
                 ("/caja/cobranza", "Caja · Cobranza")],
    "cuotas": [("/creditos/cuenta-corriente", "Créditos · Cuenta corriente"),
               ("/creditos/mora", "Créditos · Cuotas en mora"),
               ("/caja/cobranza", "Caja · Cobranza")],
    "lineas_credito": [("/creditos/lineas", "Créditos · Líneas")],
    "solicitudes_credito": [("/despacho/anexos", "Despacho · Anexo de resolución")],
    "titulares_seguro": [("/seguros/titulares", "Seguros · Titulares")],
    "polizas_agente": [("/seguros/polizas", "Seguros · Pólizas"),
                       ("/clientes/vision-360", "Clientes · Visión 360°")],
    "ctacte_seguros": [("/clientes/vision-360", "Clientes · Visión 360°")],
    "seguros_agente": [("/seguros/adicional", "Seguros · Seguro de vida adicional")],
    "regimenes_especiales": [("/seguros/regimenes", "Seguros · Regímenes especiales")],
    "juegos": [("/juegos/maestro", "Juegos · Maestro de juegos")],
    "agencias_juego": [("/juegos/liquidaciones", "Juegos · Agencias y liquidaciones")],
    "sorteos_juego": [("/juegos/sorteos", "Juegos · Control de sorteos")],
    "liquidaciones_agencia": [("/juegos/liquidaciones", "Juegos · Agencias y liquidaciones"),
                              ("/juegos/fondo-garantia", "Juegos · Fondo de garantía"),
                              ("/caja/quiniela", "Caja · Aplicativo de caja"),
                              ("/caja/deuda-agencia", "Caja · Deuda de agencia")],
    "liquidaciones_historicas": [("/juegos/fondo-garantia", "Juegos · Fondo de garantía")],
    "liquidaciones_agencia_hist": [("/caja/agencia-historico", "Caja · Histórico de agencia")],
    "caja_pagos_agencia": [("/caja/quiniela", "Caja · Aplicativo de caja")],
    "caja_pagos_agencia_hist": [("/caja/agencia-historico", "Caja · Histórico de agencia")],
    "caja_creseg": [("/caja/cobranza", "Caja · Cobranza")],
    "caja_creseg_historico": [],       # migrada, aún sin pantalla
    "tramites": [("/mesa/tramites", "Mesa · Consulta de trámites"),
                 ("/mesa/ingresados", "Mesa · Trámites ingresados")],
    "tramite_pases": [("/mesa/tramites", "Mesa · Consulta de trámites")],
    "oficinas": [("/general/oficinas", "General · Oficinas")],
    "perfiles": [("/seguridad/perfiles", "Seguridad · Perfiles")],
    "proveedores": [("/general/proveedores", "Adm. y Finanzas · Proveedores")],
    "resoluciones": [("/despacho/resoluciones", "Despacho · Resoluciones")],
    "resolucion_beneficiarios": [("/despacho/resoluciones", "Despacho · Resoluciones (beneficiarios)")],
    "modelos_resolucion": [("/despacho/modelos", "Despacho · Modelos de resoluciones")],
    "organismos": [("/general/organismos", "General · Organismos")],
    "movimientos_contables": [("/contabilidad/mayor", "Contabilidad · Balance / Mayor (real)")],
    "asientos": [("/contabilidad/libro-diario", "Contabilidad · Libro diario (app)"),
                 ("/contabilidad/balance", "Contabilidad · Balance (asientos app)")],
    "asientos_lineas": [("/contabilidad/libro-diario", "Contabilidad · Libro diario (app)")],
    "ctacte_contable_credito": [("/contabilidad/ctacte-credito", "Contabilidad · Cta. cte. contable por crédito")],
    "contabilidad_general": [("/contabilidad/general", "Contabilidad · Contabilidad general")],
    "egresos": [("/tesoreria/egresos", "Tesorería · Busca transacciones de egresos")],
    "cheques_emitidos": [("/tesoreria/cheques", "Tesorería · Cheques emitidos")],
    "ordenes_pago": [("/tesoreria/ordenes", "Tesorería · Órdenes de pago"),
                     ("/tesoreria/reporte", "Tesorería · Reporte de OP")],
    "autorizaciones_op": [("/tesoreria/autorizaciones", "Tesorería · Cupos de OP")],
    "chequeras": [("/tesoreria/chequeras", "Tesorería · Chequeras")],
    "recibos": [("/caja/cobranza", "Caja · Cobranza"),
                ("/clientes/vision-360", "Clientes · Visión 360°")],
    "eventos_auditoria": [("/seguridad/auditoria", "Seguridad · Auditoría")],
    "usuarios": [("/seguridad/usuarios", "Seguridad · Usuarios")],
}


def usos(tabla: str) -> list[dict]:
    return [{"ruta": r, "label": l} for r, l in USOS_MENU.get(tabla, [])]


def _contar(db, tabla: str) -> int:
    try:
        return db.execute(text(f'SELECT COUNT(*) FROM "{tabla}"')).scalar() or 0
    except Exception:
        return 0


def dbf_info(m: Migrador) -> dict:
    """Existencia y tamaño del/los DBF de origen (best-effort; puede ser carpeta)."""
    primera = m.dbf.split("·")[0].strip().split(" ")[0]
    ruta = os.path.join(BASES, primera)
    existe = os.path.exists(ruta)
    tamano = os.path.getsize(ruta) if (existe and os.path.isfile(ruta)) else None
    return {"ruta": ruta, "existe": existe, "tamano": tamano}


def estado(db) -> list[dict]:
    """Catálogo completo con conteos migrados y estado del DBF de origen."""
    out = []
    for m in REGISTRO:
        info = dbf_info(m)
        out.append({
            "clave": m.clave, "nombre": m.nombre, "modulo": m.modulo,
            "dbf": m.dbf, "programa": m.programa, "tabla": m.tabla, "tablas": m.tablas,
            "conversiones": [{"origen": o, "destino": d, "tipo": t} for o, d, t in m.conversiones],
            "usos": usos(m.tabla),
            "esperado": m.esperado, "migrados": _contar(db, m.tabla),
            "dbf_existe": info["existe"], "dbf_ruta": info["ruta"], "dbf_tamano": info["tamano"],
        })
    return out


# Propósito y motivo de NO migración de DBFs relevantes (investigado del código
# legacy + esquema de campos). Clave = nombre de archivo en minúscula.
NOTAS_DBF: dict[str, tuple[str, str]] = {
    # ---- Contabilidad ----
    "basectadev.dbf": ("Base de cuenta corriente de DEVENGAMIENTO contable (basectadev.prg).",
                       "El motor de devengamiento no se migró (deprioritizado); el mayor real ya está en asientos.dbf."),
    "baseopdev.dbf": ("Base de OP de devengamiento contable.", "Depende del motor de devengamiento, no migrado."),
    "crctacte.dbf": ("Cuenta corriente contable de créditos (histórico masivo).",
                     "La cta. cte. operativa de créditos se migró desde ctacte.dbf; ésta es el histórico contable, aún no priorizado."),
    "cc1.dbf": ("Cuenta corriente contable auxiliar.", "Auxiliar contable; el mayor real ya está migrado (asientos)."),
    "contgral.dbf": ("Contabilidad general / detalle del mayor.", "Redundante con asientos.dbf (libro mayor) ya migrado."),
    "agencir.dbf": ("Padrón de agencias para retenciones contables.", "Auxiliar; las agencias operativas ya están en agencias_juego."),
    "agencis.dbf": ("Padrón de agencias (contable).", "Duplicado de agencir; auxiliar contable."),
    "agereten.dbf": ("Retenciones por agencia.", "Auxiliar de retenciones; no requerido por la operación migrada."),
    "contrib.dbf": ("Contribuyentes / alícuotas de IIBB.", "Parámetro contable; IIBB ya se calcula en Juegos con dato real."),
    "padron.dbf": ("Padrón contable auxiliar.", "Tabla de apoyo, no operativa."),
    "ctblecred.dbf": ("Cuentas contables de créditos (vacía en el backup).", "0 registros; nada para migrar."),
    # ---- Caja / Juegos ----
    "cajaforpag.dbf": ("Formas de pago de caja (quiniela).", "El detalle de pagos ya se migró en cajapagos → liquidaciones/pagos de agencia."),
    "cierrejuegos.dbf": ("Cierres de caja de juegos por día.", "Reporte de cierre; se recalcula sobre las liquidaciones migradas."),
    "cierrecaja.dbf": ("Cierres de caja por día.", "Se recalcula sobre los datos migrados (cierre en la app)."),
    "cierremoneda.dbf": ("Cierres por moneda (pesos/bonos).", "Se recalcula en el cierre de la app."),
    "cj_liqhis.dbf": ("HISTÓRICO de liquidaciones de agencia de caja (1,37M).",
                      "El histórico de agencias ya se cubre con jghisliq → liquidaciones_historicas; este otro histórico no se priorizó."),
    "cj_paghis.dbf": ("Histórico de pagos de agencia de caja.", "Histórico voluminoso; la operación usa cajapagos migrado."),
    "cj_crsghis.dbf": ("Histórico de crédito/seguro cobrado en caja (cajacreseg).", "Histórico; el vigente ya está migrado (caja_creseg)."),
    "cj_fpaghis.dbf": ("Histórico de formas de pago de caja.", "Histórico auxiliar, no operativo."),
    "jjimpjue.dbf": ("Importación histórica de jugadas por sorteo (5,4M; l1pandemia.prg).",
                     "Detalle de jugadas por sorteo; no requerido para la operación (se usa la liquidación agregada)."),
    "liquidaciones.dbf": ("Liquidaciones de agencia (tabla VFP intermedia, 408k).",
                          "La operación se migró desde cajaliq (vigentes) + jghisliq (histórico); esta intermedia quedó pendiente de consolidar."),
    "ingbruq.dbf": ("Ingresos brutos de quiniela (resumen).", "IIBB ya se calcula con dato real en Juegos."),
    "cjcontrol.dbf": ("Control de cajero por caja.", "Se reconstruye en el control de caja de la app."),
    # ---- Seguros ----
    "liqsegur.dbf": ("Liquidación/devengamiento masivo de seguros (10,1M).",
                     "Devengamiento histórico enorme; la liquidación operativa se cubre por cuota/póliza migradas."),
    "liqsegur_menores_2014.dbf": ("Liquidación de seguros histórica pre-2014 (9,1M).", "Histórico masivo, no priorizado."),
    "ccseguros.dbf": ("Cuenta corriente de seguros por agente.", ""),  # (ahora migrada)
    "benefici.dbf": ("Beneficiarios de seguros (por agente).", "Padrón de beneficiarios; los regímenes/beneficiarios operativos ya están en el modelo."),
    "familia.dbf": ("Grupo familiar del agente (seguros).", "Padrón auxiliar de familiares."),
    "jubilado.dbf": ("Padrón de jubilados con seguro.", "Auxiliar; los jubilados de crédito (Ley 5094) ya se marcan en créditos."),
    "activos.dbf": ("Padrón de agentes activos con seguro.", "Padrón auxiliar; los titulares ya están migrados (122k)."),
    "aux_act.dbf": ("Auxiliar de activos por período.", "Tabla intermedia de proceso."),
    "requisitos.dbf": ("Requisitos presentados por seguro/CUIL.", "Auxiliar de trámite de seguros."),
    "liquid_dat.dbf": ("Datos de liquidación de seguros.", "Auxiliar del proceso de liquidación."),
}


def _nota(fn: str, campos: list[str], usado: bool) -> tuple[str, str]:
    """Devuelve (propósito, motivo). Usa NOTAS_DBF o infiere por patrón.
    Si está migrada, muestra el propósito pero sin motivo de 'no migra'."""
    low = fn.lower()
    base = NOTAS_DBF.get(low)
    if usado:
        return (base[0] if base else "", "")
    if base:
        return base
    import re
    if re.match(r"iejue\d+", low):
        return ("Exportación diaria de ingreso de jugadas por sorteo/fecha (agencia, juego, importe).",
                "Archivo diario por fecha; la operación usa la liquidación agregada, no el detalle por sorteo.")
    if low.endswith((".bak", "bak.dbf")) or "copia" in low or low.startswith("~") or "tmp" in low or "temp" in low or "_old" in low:
        return ("Respaldo / archivo temporal.", "Copia o temporal, no es la tabla operativa.")
    if "his" in low:
        return ("Tabla histórica.", "Histórico; la operación trabaja sobre las tablas vigentes ya migradas.")
    if low.startswith("cierre"):
        return ("Cierre por período/día.", "Se recalcula en la app sobre los datos migrados.")
    return ("(sin catalogar)", "Auxiliar/no operativa; se puede migrar si se necesita — avisar.")


def _cabecera_dbf(path: str) -> dict:
    """Lee SOLO la cabecera del .dbf → nº de registros y nombres de campos.
    Barato (no lee el archivo entero, sirve para inventariar DBFs enormes)."""
    import struct
    try:
        with open(path, "rb") as f:
            head = f.read(32)
            if len(head) < 32:
                return {"registros": None, "campos": []}
            registros = struct.unpack("<I", head[4:8])[0]
            hlen = struct.unpack("<H", head[8:10])[0]
            resto = f.read(max(0, hlen - 32))
        campos = []
        for i in range(0, len(resto), 32):
            chunk = resto[i:i + 32]
            if not chunk or chunk[0:1] in (b"\r", b"\x0d"):
                break
            if len(chunk) < 11:
                break
            nombre = chunk[0:11].split(b"\x00")[0].decode("latin-1", "ignore").strip()
            if nombre:
                campos.append(nombre)
        return {"registros": registros, "campos": campos}
    except Exception:
        return {"registros": None, "campos": []}


def inventario() -> dict:
    """Inventario de TODOS los .dbf del backup, por carpeta, indicando cuáles se
    usan para migrar (a qué migrador/tabla) y cuáles no, con nº de registros y
    campos de cada uno."""
    usados: dict[str, dict] = {}
    for clave, rutas in DBFS_USADOS.items():
        m = REGISTRO_POR_CLAVE.get(clave)
        mapeo = [{"origen": o, "destino": d} for o, d, _ in (m.conversiones if m else [])]
        for r in rutas:
            usados[r.lower().replace("\\", "/")] = {
                "clave": clave, "migrador": m.nombre if m else clave,
                "tabla": m.tabla if m else None, "mapeo": mapeo}

    carpetas = []
    if os.path.isdir(BASES):
        for entrada in sorted(os.listdir(BASES)):
            full = os.path.join(BASES, entrada)
            if not os.path.isdir(full):
                continue
            dbfs = []
            try:
                archivos = sorted(os.listdir(full))
            except OSError:
                archivos = []
            for fn in archivos:
                if not fn.lower().endswith(".dbf"):
                    continue
                fpath = os.path.join(full, fn)
                if not os.path.isfile(fpath):
                    continue
                rel = f"{entrada}/{fn}"
                cab = _cabecera_dbf(fpath)
                u = usados.get(rel.lower())
                proposito, motivo = _nota(fn, cab["campos"], bool(u))
                dbfs.append({
                    "archivo": fn, "ruta": rel, "tamano": os.path.getsize(fpath),
                    "registros": cab["registros"], "campos": cab["campos"],
                    "usado": bool(u), "migrador": u["migrador"] if u else None,
                    "tabla": u["tabla"] if u else None,
                    "mapeo": u["mapeo"] if u else [],
                    "proposito": proposito, "motivo": motivo,
                })
            if dbfs:
                carpetas.append({
                    "carpeta": entrada, "cantidad": len(dbfs),
                    "usados": sum(1 for d in dbfs if d["usado"]), "dbfs": dbfs})
    return {"bases": BASES, "carpetas": carpetas}


def _reset_tablas(tablas: list[str]) -> None:
    if not tablas:
        return
    backend = engine.url.get_backend_name()
    with engine.begin() as conn:
        if backend.startswith("postgres"):
            lista = ", ".join(f'"{t}"' for t in tablas)
            conn.execute(text(f"TRUNCATE {lista} RESTART IDENTITY CASCADE"))
        else:
            for t in tablas:   # ya vienen hijas primero
                conn.execute(text(f'DELETE FROM "{t}"'))


def ejecutar(clave: str, *, reset: bool = False) -> dict:
    """Corre un migrador. Con reset=True trunca sus tablas antes de recargar
    (necesario para re-migrar cuando cambian los DBFs)."""
    m = REGISTRO_POR_CLAVE.get(clave)
    if not m:
        raise KeyError(clave)
    if reset and m.tablas:
        _reset_tablas(m.tablas)
    m.loader(BASES)
    db = SessionLocal()
    try:
        return {"clave": clave, "migrados": _contar(db, m.tabla)}
    finally:
        db.close()
