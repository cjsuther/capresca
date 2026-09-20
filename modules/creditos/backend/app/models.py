"""Modelos SQLAlchemy — núcleo de dominio (módulos General/Seguridad y Créditos).

Derivados del catálogo de datos inferido del VFP (ver salida/catalogo_datos.md).
Se moderniza el nombre de columna y se conserva, en comentario, el campo VFP
original para facilitar el ETL desde los DBF.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    String, Integer, BigInteger, Numeric, Date, DateTime, Boolean, ForeignKey,
    Text, Index, UniqueConstraint, JSON, func, event,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Usuario(Base):
    """Usuarios del sistema (VFP: agjsgeneral!usuarios + symdeperf.perfil)."""
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    nombre: Mapped[str] = mapped_column(String(80), default="")
    password_hash: Mapped[str] = mapped_column(String(200))
    perfil: Mapped[str] = mapped_column(String(6), index=True)  # ADMG, xCJ, xCR...
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    creado: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Organismo(Base):
    """Organismos empleadores (VFP: agjsgeneral!organismos)."""
    __tablename__ = "organismos"

    # organo real tiene hasta 12 dígitos (H-015): BigInteger en Postgres, Integer
    # en SQLite (para el autoincrement por rowid en el seed demo).
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True)  # organo
    codigo: Mapped[str] = mapped_column(String(15), index=True)  # corga
    nombre: Mapped[str] = mapped_column(String(120))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)

    clientes: Mapped[list["Cliente"]] = relationship(back_populates="organismo")


class Cliente(Base):
    """Clientes / agentes (VFP: maeclientes + maestrodio consolidados)."""
    __tablename__ = "clientes"

    id: Mapped[int] = mapped_column(primary_key=True)
    id_cliente: Mapped[str] = mapped_column(String(15), unique=True, index=True)  # cidcliente
    cuil: Mapped[str] = mapped_column(String(11), unique=True, index=True)  # ccuil (único: la DB es árbitro, H-154)
    dni: Mapped[str] = mapped_column(String(9), default="")        # edni
    apellido_nombre: Mapped[str] = mapped_column(String(80))       # capenom
    sexo: Mapped[str] = mapped_column(String(1), default="")       # csexo
    fecha_nacimiento: Mapped[date | None] = mapped_column(Date)    # fnacim
    domicilio: Mapped[str] = mapped_column(String(120), default="")  # cdomicilio
    barrio: Mapped[str] = mapped_column(String(40), default="")    # cbarrio
    localidad: Mapped[str] = mapped_column(String(40), default="")  # clocalidad
    telefono: Mapped[str] = mapped_column(String(30), default="")  # ctelefono
    email: Mapped[str] = mapped_column(String(80), default="")     # cemail
    cbu: Mapped[str] = mapped_column(String(23), default="")       # ccbucta
    debito_automatico: Mapped[bool] = mapped_column(Boolean, default=False)  # ldebauto
    sueldo: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)  # nsueldo
    categoria_funcion: Mapped[str] = mapped_column(String(10), default="")  # ccatfun
    fecha_ingreso: Mapped[date | None] = mapped_column(Date)       # ffperm
    tipo_cliente: Mapped[int] = mapped_column(Integer, default=0)  # ntipocli
    baja: Mapped[bool] = mapped_column(Boolean, default=False)     # lbaja
    fecha_baja: Mapped[date | None] = mapped_column(Date)          # fecbaja
    motivo_baja: Mapped[str] = mapped_column(String(60), default="")  # cmotbaja

    organismo_id: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), ForeignKey("organismos.id"))
    organismo: Mapped["Organismo"] = relationship(back_populates="clientes")

    solicitudes: Mapped[list["Solicitud"]] = relationship(back_populates="cliente")


class LineaCredito(Base):
    """Líneas de crédito (VFP: agjscreditos!lineacred)."""
    __tablename__ = "lineas_credito"

    id: Mapped[int] = mapped_column(primary_key=True)             # linea / no_linea
    nombre: Mapped[str] = mapped_column(String(80))
    cartera: Mapped[int] = mapped_column(Integer, index=True)     # cartera (ver domain.carteras)
    tipo_calculo: Mapped[int] = mapped_column(Integer, default=1)  # 1..5
    tna: Mapped[Decimal] = mapped_column(Numeric(7, 3), default=0)  # tasa nominal anual %
    tasa_mora_diaria: Mapped[Decimal] = mapped_column(Numeric(9, 5), default=0)  # nmoradia
    iva: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("21"))
    por_afecta: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("30"))  # por_afecta
    porcent_pp: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)  # umbral previo pago
    seguro_pct: Mapped[Decimal] = mapped_column(Numeric(9, 5), default=0)
    gastos_adm_pct: Mapped[Decimal] = mapped_column(Numeric(9, 5), default=0)
    plazo_max: Mapped[int] = mapped_column(Integer, default=60)
    monto_max: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    plazo_gracia: Mapped[int] = mapped_column(Integer, default=0)          # plazo de gracia
    paga_interes_gracia: Mapped[bool] = mapped_column(Boolean, default=False)  # PIG
    suma_int_gracia_capital: Mapped[bool] = mapped_column(Boolean, default=False)  # SIGC
    admite_previo_pago: Mapped[bool] = mapped_column(Boolean, default=False)   # ISIN/admite PP
    cta_contable: Mapped[str] = mapped_column(String(20), default="")     # Cta.Ctble.
    compania_seguros_id: Mapped[int | None] = mapped_column(
        ForeignKey("companias_seguros.id"))
    activa: Mapped[bool] = mapped_column(Boolean, default=True)            # Hab


class MovimientoCta(Base):
    """Movimiento de cuenta corriente de un crédito (VFP: ctacte)."""
    __tablename__ = "movimientos_cta"

    id: Mapped[int] = mapped_column(primary_key=True)
    credito_id: Mapped[int] = mapped_column(Integer, index=True)   # nno_credit
    cuota: Mapped[int] = mapped_column(Integer, default=0)         # nno_cuota
    fecha: Mapped[date | None] = mapped_column(Date)              # tfecha
    tipo: Mapped[str] = mapped_column(String(4), default="")       # ctipo (D/C mov)
    debitos: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    creditos: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    capital: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    interes: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    iva: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    punitorio: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    no_recibo: Mapped[int] = mapped_column(Integer, default=0)


class Requisito(Base):
    """Requisitos para créditos por línea (VFP: frm305150000requisitos)."""
    __tablename__ = "requisitos"

    id: Mapped[int] = mapped_column(primary_key=True)
    linea_id: Mapped[int | None] = mapped_column(ForeignKey("lineas_credito.id"))
    descripcion: Mapped[str] = mapped_column(String(150))
    obligatorio: Mapped[bool] = mapped_column(Boolean, default=True)


class Gasista(Base):
    """Gasistas / Institutos matriculados (VFP: frm305250000gasistas)."""
    __tablename__ = "gasistas"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(80))
    matricula: Mapped[str] = mapped_column(String(30), default="")
    cuit: Mapped[str] = mapped_column(String(11), default="")
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class MontoPeriodo(Base):
    """Monto máximo a prestar por línea y período (VFP: frm305300000montosperiodos)."""
    __tablename__ = "montos_periodo"

    id: Mapped[int] = mapped_column(primary_key=True)
    linea_id: Mapped[int] = mapped_column(ForeignKey("lineas_credito.id"))
    periodo: Mapped[str] = mapped_column(String(7), index=True)   # YYYY-MM
    monto_maximo: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)


class Solicitud(Base):
    """Solicitudes de crédito (VFP: agjscreditos!solicitud, ~158 campos)."""
    __tablename__ = "solicitudes"

    id: Mapped[int] = mapped_column(primary_key=True)            # no_solicitud
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id"), index=True)
    linea_id: Mapped[int] = mapped_column(ForeignKey("lineas_credito.id"))
    estado: Mapped[str] = mapped_column(String(1), default="I", index=True)  # I,A,B,...
    fecha_solicitud: Mapped[date] = mapped_column(Date, server_default=func.now())  # fecha_soli
    monto_solicitado: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)  # montosol
    cantidad_cuotas: Mapped[int] = mapped_column(Integer, default=0)  # cant_cuotas
    tna: Mapped[Decimal] = mapped_column(Numeric(7, 3), default=0)     # tna
    cuota_fija: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)  # tipo_calculo=5
    debito_automatico: Mapped[bool] = mapped_column(Boolean, default=True)  # debauto
    # Garantes (VFP: ga_*, g2_*, g3_*, g4_*)
    garante1_cuil: Mapped[str] = mapped_column(String(11), default="")
    garante2_cuil: Mapped[str] = mapped_column(String(11), default="")
    garante3_cuil: Mapped[str] = mapped_column(String(11), default="")
    garante4_cuil: Mapped[str] = mapped_column(String(11), default="")
    # Conceptos reales (VFP: solicitud, 215 campos) — ver hallazgo H-011
    gastos_originacion: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)      # igori
    iva_gastos_originacion: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)  # nivaori
    quebranto: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)               # iquebranto
    iva_quebranto: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)           # nivaqeb
    sellado: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)                 # isellado
    iva_sellado: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)             # nivasel
    gastos_admin: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)            # igastos
    cft: Mapped[Decimal] = mapped_column(Numeric(9, 3), default=0)                      # costo financiero total
    indexado: Mapped[bool] = mapped_column(Boolean, default=False)
    credito_previo_pago: Mapped[int | None] = mapped_column(Integer)   # no_credpp
    importe_previo_pago: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)  # importepp
    numero_resolucion: Mapped[str] = mapped_column(String(20), default="")  # no_resol
    observaciones: Mapped[str] = mapped_column(Text, default="")

    cliente: Mapped["Cliente"] = relationship(back_populates="solicitudes")
    linea: Mapped["LineaCredito"] = relationship()


class CreditoJubilado(Base):
    """Crédito/subsidio a jubilados — Ley 5094 (VFP: sol_jubi)."""
    __tablename__ = "creditos_jubilado"

    id: Mapped[int] = mapped_column(primary_key=True)              # no_solicit
    # no_benefic real tiene hasta 12 dígitos (H-015) → BigInteger
    beneficiario_nro: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), default=0)  # no_benefic
    cuil: Mapped[str] = mapped_column(String(11), index=True, default="")
    apellido_nombre: Mapped[str] = mapped_column(String(80))       # ape_nom
    domicilio: Mapped[str] = mapped_column(String(120), default="")
    localidad: Mapped[str] = mapped_column(String(40), default="")
    departamento: Mapped[str] = mapped_column(String(40), default="")  # depto
    haberes: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    monto: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    cantidad_cuotas: Mapped[int] = mapped_column(Integer, default=0)
    liquidada: Mapped[bool] = mapped_column(Boolean, default=False)
    numero_resolucion: Mapped[str] = mapped_column(String(20), default="")
    prorroga: Mapped[bool] = mapped_column(Boolean, default=False)
    fecha_alta: Mapped[date | None] = mapped_column(Date)


class CuotaJubilado(Base):
    """Cuota de un crédito de jubilado (VFP: jub_ctas)."""
    __tablename__ = "cuotas_jubilado"

    id: Mapped[int] = mapped_column(primary_key=True)
    credito_jubilado_id: Mapped[int] = mapped_column(
        ForeignKey("creditos_jubilado.id"), index=True)             # no_solicit
    cuil: Mapped[str] = mapped_column(String(11), default="")
    numero: Mapped[int] = mapped_column(Integer, default=0)         # no_cuota
    valor: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)  # valor_cta
    fecha_vencimiento: Mapped[date | None] = mapped_column(Date)
    pagada: Mapped[bool] = mapped_column(Boolean, default=False)
    fecha_pago: Mapped[date | None] = mapped_column(Date)
    numero_resolucion: Mapped[str] = mapped_column(String(20), default="")
    no_op: Mapped[int] = mapped_column(Integer, default=0)


class Credito(Base):
    """Créditos activos (VFP: agjscreditos!crcliact)."""
    __tablename__ = "creditos"

    id: Mapped[int] = mapped_column(primary_key=True)           # no_credito
    # solicitud_id es nullable: los créditos históricos del backup no tienen
    # una solicitud modelada; se usa linea_id (denormalizado) para el cálculo.
    solicitud_id: Mapped[int | None] = mapped_column(ForeignKey("solicitudes.id"))
    linea_id: Mapped[int | None] = mapped_column(ForeignKey("lineas_credito.id"))
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id"), index=True)
    capital: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    saldo_capital: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)  # saldo_cap
    fecha_otorgamiento: Mapped[date | None] = mapped_column(Date)
    estado: Mapped[str] = mapped_column(String(1), default="A")  # A activo, C cancelado, B baja/anulado
    motivo_baja: Mapped[str] = mapped_column(String(120), default="")
    fecha_baja: Mapped[date | None] = mapped_column(Date)
    usuario_baja: Mapped[str] = mapped_column(String(30), default="")

    cuotas: Mapped[list["Cuota"]] = relationship(back_populates="credito")


class Cuota(Base):
    """Cuotas del plan (VFP: agjscreditos!maecuotas)."""
    __tablename__ = "cuotas"

    id: Mapped[int] = mapped_column(primary_key=True)
    credito_id: Mapped[int] = mapped_column(ForeignKey("creditos.id"), index=True)
    numero: Mapped[int] = mapped_column(Integer)               # ncuota
    fecha_vencimiento: Mapped[date] = mapped_column(Date)      # fecha_vto
    saldo_capital: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    amortizacion: Mapped[Decimal] = mapped_column(Numeric(14, 2))  # capital
    interes: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    iva_interes: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    seguro: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    iva_seguro: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    gastos_adm: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    iva_gastos_adm: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    total_pagado: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    estado: Mapped[str] = mapped_column(String(1), default="A")  # A,M,P (pagada)
    # Datos del pago en caja (VFP maecuotas: FECHA_PAGO/NRECIBO/VIA_PAGO/USUARIO_PA)
    fecha_pago: Mapped[date | None] = mapped_column(Date, index=True)
    nro_recibo: Mapped[int] = mapped_column(Integer, default=0)
    via_pago: Mapped[str] = mapped_column(String(10), default="")
    usuario_pago: Mapped[str] = mapped_column(String(30), default="")

    credito: Mapped["Credito"] = relationship(back_populates="cuotas")


class TurnoCredito(Base):
    """Turno otorgado para solicitar un crédito (VFP: turnos). Distinto del
    turno de Mesa de Entradas: es el cupo/orden para presentar la solicitud."""
    __tablename__ = "turnos_credito"

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[str] = mapped_column(String(10), default="", index=True)  # CTIPO TODO/AGAP
    numero: Mapped[int] = mapped_column(Integer, default=0)                # NTURNO
    periodo: Mapped[str] = mapped_column(String(6), default="", index=True)  # PERIODO YYYYMM (LEFT(DTOS(fecha),6))
    fecha: Mapped[date | None] = mapped_column(Date, index=True)
    cuil: Mapped[str] = mapped_column(String(11), default="", index=True)
    apellido_nombre: Mapped[str] = mapped_column(String(80), default="")
    linea: Mapped[int] = mapped_column(Integer, default=0)                 # NLINEA
    sueldo: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    usado: Mapped[bool] = mapped_column(Boolean, default=False)            # LUSADO
    autorizado: Mapped[bool] = mapped_column(Boolean, default=False)       # LAUTORIZA


class EventoAuditoria(Base):
    """Evento de auditoría (VFP: agjsgeneral!auditoria, 6,5M registros)."""
    __tablename__ = "eventos_auditoria"

    id: Mapped[int] = mapped_column(primary_key=True)
    fecha_hora: Mapped[datetime] = mapped_column(DateTime, index=True, server_default=func.now())
    maquina: Mapped[str] = mapped_column(String(40), default="")
    usuario: Mapped[str] = mapped_column(String(40), index=True, default="")
    sistema: Mapped[str] = mapped_column(String(20), default="")
    perfil: Mapped[str] = mapped_column(String(8), default="")
    proceso: Mapped[str] = mapped_column(String(60), default="")
    opcion: Mapped[str] = mapped_column(String(80), default="")


class AuditoriaCambio(Base):
    """Rastro de auditoría del sistema NUEVO: quién cambió qué, con antes/después + IP.

    Distinto de `EventoAuditoria` (log VFP migrado, sólo el hecho): acá guardamos el
    diff de la mutación (`datos_anteriores`/`datos_nuevos`/`cambios`), la IP de origen y
    el resultado (OK/ERROR/RECHAZADO). Idea incorporada del memo de migración de créditos:
    "para un sistema de créditos, auditoría desde el principio, con antes/después e IP".
    """
    __tablename__ = "auditoria_cambios"

    id: Mapped[int] = mapped_column(primary_key=True)
    fecha_hora: Mapped[datetime] = mapped_column(DateTime, index=True, server_default=func.now())
    usuario: Mapped[str] = mapped_column(String(40), index=True, default="")
    perfil: Mapped[str] = mapped_column(String(8), default="")
    ip: Mapped[str] = mapped_column(String(64), default="")
    entidad: Mapped[str] = mapped_column(String(40), index=True, default="")   # Solicitud, Contrato, Credito…
    entidad_id: Mapped[str] = mapped_column(String(40), default="")
    operacion: Mapped[str] = mapped_column(String(30), index=True, default="")  # ALTA, ORIGINAR, BAJA, APROBAR…
    resultado: Mapped[str] = mapped_column(String(12), default="OK")            # OK, ERROR, RECHAZADO
    detalle: Mapped[str] = mapped_column(String(300), default="")
    datos_anteriores: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    datos_nuevos: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    cambios: Mapped[dict | None] = mapped_column(JSON, nullable=True)           # {campo: [antes, después]}


class Parametro(Base):
    """Parámetros generales (VFP: agjsgeneral!paramgral)."""
    __tablename__ = "parametros"

    id: Mapped[int] = mapped_column(primary_key=True)
    clave: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    valor: Mapped[str] = mapped_column(String(200))
    descripcion: Mapped[str] = mapped_column(String(200), default="")
    ambito: Mapped[str] = mapped_column(String(20), default="general", index=True)  # general|creditos|contabilidad (H-197)


class Recibo(Base):
    """Recibo de cobranza (VFP: agjscaja!cajapagos + cajacreseg)."""
    __tablename__ = "recibos"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Nº de recibo generado (max+1 global): unicidad garantizada por la DB (árbitro) contra la carrera
    # de dos cajeros concurrentes emitiendo el mismo número. La tabla es 100% del sistema nuevo.
    numero: Mapped[int] = mapped_column(Integer, unique=True, index=True)   # no_recibo
    fecha_pago: Mapped[date] = mapped_column(Date, index=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id"), index=True)
    credito_id: Mapped[int] = mapped_column(ForeignKey("creditos.id"), index=True)
    cajero: Mapped[str] = mapped_column(String(30))               # usuario que cobra
    via_pago: Mapped[str] = mapped_column(String(20), default="EFECTIVO")
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    estado: Mapped[str] = mapped_column(String(1), default="E")   # E emitido, A anulado
    creado: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    pagos: Mapped[list["PagoCuota"]] = relationship(back_populates="recibo")


class PagoCuota(Base):
    """Imputación de un recibo a una cuota (con desglose y mora)."""
    __tablename__ = "pagos_cuota"

    id: Mapped[int] = mapped_column(primary_key=True)
    recibo_id: Mapped[int] = mapped_column(ForeignKey("recibos.id"), index=True)
    cuota_id: Mapped[int] = mapped_column(ForeignKey("cuotas.id"), index=True)
    capital: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    interes: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    iva_interes: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    seguro: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    gastos_adm: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    interes_punitorio: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    iva_punitorio: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    dias_mora: Mapped[int] = mapped_column(Integer, default=0)
    total_pagado: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)

    recibo: Mapped["Recibo"] = relationship(back_populates="pagos")
    cuota: Mapped["Cuota"] = relationship()


class Juego(Base):
    """Maestro de juegos (VFP: maejuegos). Cada juego/modalidad con su comisión."""
    __tablename__ = "juegos"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[int] = mapped_column(Integer, index=True)          # CODIGO
    modalidad: Mapped[int] = mapped_column(Integer, default=0)        # MODALIDAD
    cod_afip: Mapped[int] = mapped_column(Integer, default=0)         # NCODAFIP
    denominacion: Mapped[str] = mapped_column(String(40), default="")  # DENOMINACI
    com_agencia: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=0)    # COM_AGENCI %
    com_subagencia: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=0)  # COM_SUBAGE %


class Sorteo(Base):
    """Sorteo/jugada de un juego (VFP: maejugadas). Calendario de sorteos."""
    __tablename__ = "sorteos_juego"

    id: Mapped[int] = mapped_column(primary_key=True)
    cod_juego: Mapped[int] = mapped_column(Integer, index=True)       # COD_JUEGO
    no_sorteo: Mapped[int] = mapped_column(Integer, index=True)       # NO_SORTEO
    fecha_sorteo: Mapped[date | None] = mapped_column(Date)           # FECHA_SORT
    fecha_vto: Mapped[date | None] = mapped_column(Date)              # FECHA_VTO
    importado_caja: Mapped[bool] = mapped_column(Boolean, default=False)  # CAJAIMPORT


class AgenciaJuego(Base):
    """Agencia de juegos/quiniela (VFP: agjsjuegos/agenjuegos)."""
    __tablename__ = "agencias_juego"

    id: Mapped[int] = mapped_column(primary_key=True)
    numero: Mapped[int] = mapped_column(Integer, index=True)          # no_agencia
    subagencia: Mapped[int] = mapped_column(Integer, default=0)       # no_subagen
    codigo: Mapped[int] = mapped_column(Integer, default=0)           # cod_agenci
    interior: Mapped[bool] = mapped_column(Boolean, default=False)
    # Juegos que ofrece
    quiniela: Mapped[bool] = mapped_column(Boolean, default=False)
    quini6: Mapped[bool] = mapped_column(Boolean, default=False)
    loto: Mapped[bool] = mapped_column(Boolean, default=False)
    brinco: Mapped[bool] = mapped_column(Boolean, default=False)
    prode: Mapped[bool] = mapped_column(Boolean, default=False)
    telekino: Mapped[bool] = mapped_column(Boolean, default=False)
    activa: Mapped[bool] = mapped_column(Boolean, default=True)


class LiquidacionAgencia(Base):
    """Liquidación de una agencia por sorteo (VFP: cajaliq)."""
    __tablename__ = "liquidaciones_agencia"

    id: Mapped[int] = mapped_column(primary_key=True)
    cod_agencia: Mapped[int] = mapped_column(Integer, index=True, default=0)  # cod_agenci
    no_agencia: Mapped[int] = mapped_column(Integer, index=True)
    subagencia: Mapped[int] = mapped_column(Integer, default=0)
    cod_juego: Mapped[int] = mapped_column(Integer, default=0)         # cod_juego
    juego: Mapped[str] = mapped_column(String(30), default="")         # cjuego
    no_sorteo: Mapped[int] = mapped_column(Integer, index=True)
    fecha_sorteo: Mapped[date | None] = mapped_column(Date)
    interior: Mapped[bool] = mapped_column(Boolean, default=False)     # INTERIOR (capital/interior)
    moneda: Mapped[str] = mapped_column(String(1), default="$")        # MONEDA ($/B)
    recaudacion: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    premios: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    com_premios: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)  # COM_PREMIO
    comision_agencia: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    comision_subagencia: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    multas: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    ing_brutos: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)   # ING_BRUTOS (retención)
    fdo_gtia: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)     # FDO_GTIA (fondo de garantía)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    intereses: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    iva: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    total_gral: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    fecha_vto: Mapped[date | None] = mapped_column(Date)
    pagado: Mapped[bool] = mapped_column(Boolean, default=False)
    fecha_pago: Mapped[date | None] = mapped_column(Date)
    cajero: Mapped[str] = mapped_column(String(20), default="")
    no_recibo: Mapped[int] = mapped_column(Integer, default=0, index=True)


class CajaCreSeg(Base):
    """Cola/cobros de caja de Créditos, Seguros y Extraordinarios (VFP: cajacreseg).
    Cada ítem cobrado por caja, con su interés/IVA normal y punitorio. Es la fuente
    real de la cobranza de créditos/seguros en caja (menú 22515) y de sus reportes."""
    __tablename__ = "caja_creseg"

    id: Mapped[int] = mapped_column(primary_key=True)               # NORDEN
    origen: Mapped[str] = mapped_column(String(4), index=True)      # CRED/SEGU/EXTR/JUEG
    no_credito: Mapped[int] = mapped_column(Integer, default=0, index=True)
    cuil: Mapped[str] = mapped_column(String(11), default="")
    dni: Mapped[str] = mapped_column(String(9), default="")
    apellido_nombre: Mapped[str] = mapped_column(String(80), default="")  # APENOM
    cuota: Mapped[int] = mapped_column(Integer, default=0)          # CUALCUO
    moncuo: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    interes: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)     # interés normal
    iva_interes: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)  # IVAIN
    seguro: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)      # NSEG
    iva_seguro: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)  # NIVASEG
    gastos: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    iva_gastos: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)  # NIVAADM
    interes_punit: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)   # INTERESES
    iva_punit: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)       # IVA
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    total_gral: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    moneda: Mapped[str] = mapped_column(String(1), default="$")
    cajero: Mapped[str] = mapped_column(String(20), default="")
    fecha_pago: Mapped[date | None] = mapped_column(Date, index=True)
    pagado: Mapped[bool] = mapped_column(Boolean, default=False)
    revertida: Mapped[bool] = mapped_column(Boolean, default=False)   # LREVERTIDA
    no_recibo: Mapped[int] = mapped_column(Integer, default=0, index=True)  # RECOFI
    mes: Mapped[int] = mapped_column(Integer, default=0)
    ano: Mapped[int] = mapped_column(Integer, default=0)
    coding: Mapped[int] = mapped_column(Integer, default=0, index=True)   # CODING (tipo ingreso)
    subing: Mapped[int] = mapped_column(Integer, default=0)               # SUBING
    ctactble: Mapped[str] = mapped_column(String(20), default="")


class CajaPagoAgencia(Base):
    """Recibo de cobro de una agencia de quiniela (VFP: cajapagos). Doble moneda
    (bonos/pesos), vuelto por moneda y premios descontados. Reconstruye el
    Aplicativo de Caja (frm225050000aplicaj / menú 22505)."""
    __tablename__ = "caja_pagos_agencia"

    id: Mapped[int] = mapped_column(primary_key=True)
    cod_agencia: Mapped[int] = mapped_column(Integer, index=True)      # cod_agenci
    fecha_pago: Mapped[date | None] = mapped_column(Date, index=True)
    origen: Mapped[str] = mapped_column(String(4), default="JUEG")
    # Nº de recibo de cobranza de agencia (max+1 global): unicidad por la DB (árbitro). H-108.
    no_recibo: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    bonos: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)          # adeudado bonos
    pesos: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)          # adeudado pesos
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    cobrado_bonos: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    cobrado_pesos: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    cobrado_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    vuelto_bonos: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    vuelto_pesos: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    premios_bonos: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    premios_pesos: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    cajero: Mapped[str] = mapped_column(String(20), default="")
    anulado: Mapped[bool] = mapped_column(Boolean, default=False)


class TramiteTipo(Base):
    """Catálogo de tipos de trámite histórico (VFP: tipotram): N=Nota, E*=Expedientes."""
    __tablename__ = "tramite_tipos"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(4), index=True, default="")  # TIPO
    descripcion: Mapped[str] = mapped_column(String(60), default="")        # DESCRIPCIO
    corta: Mapped[str] = mapped_column(String(15), default="")              # DES_RED


class Tramite(Base):
    """Trámite / nota / expediente de Mesa de Entradas (VFP: tramites, 82k).
    Identificado por tipo+letra+número+año."""
    __tablename__ = "tramites"

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[str] = mapped_column(String(4), index=True, default="")    # ID_TRAMITE
    letra: Mapped[str] = mapped_column(String(2), default="")               # ID_LETRA
    numero: Mapped[int] = mapped_column(Integer, index=True, default=0)     # ID_NRO
    anio: Mapped[int] = mapped_column(Integer, index=True, default=0)       # ID_ANO
    sentido: Mapped[str] = mapped_column(String(1), default="")             # I_D (I/D)
    referencia: Mapped[str] = mapped_column(String(120), default="")
    iniciador: Mapped[str] = mapped_column(String(80), default="")         # NOMBRE_INI/INICIADOR
    asegurado: Mapped[str] = mapped_column(String(80), default="")         # NOMBRE_ASE
    destino: Mapped[str] = mapped_column(String(40), default="")
    estado: Mapped[str] = mapped_column(String(1), default="", index=True)  # A/C/B
    oficina_actual: Mapped[int] = mapped_column(Integer, default=0)
    hojas: Mapped[int] = mapped_column(Integer, default=0)
    fecha_alta: Mapped[date | None] = mapped_column(Date, index=True)


class Proveedor(Base):
    """Proveedor (VFP: proveedores). Beneficiario de OP por licitaciones/compras."""
    __tablename__ = "proveedores"

    id: Mapped[int] = mapped_column(primary_key=True)   # NPROVEEDOR
    cuit: Mapped[str] = mapped_column(String(11), index=True, default="")
    razon_social: Mapped[str] = mapped_column(String(80), default="")
    contacto: Mapped[str] = mapped_column(String(60), default="")
    domicilio: Mapped[str] = mapped_column(String(80), default="")
    localidad: Mapped[str] = mapped_column(String(40), default="")
    departamento: Mapped[str] = mapped_column(String(40), default="")
    tipo_iva: Mapped[str] = mapped_column(String(4), default="")   # RI/MT/EX...
    ingresos_brutos: Mapped[str] = mapped_column(String(15), default="")
    anulado: Mapped[bool] = mapped_column(Boolean, default=False)


class Perfil(Base):
    """Rol de acceso del sistema (origen VFP: maeperfil). Es el 'Rol' del RBAC:
    `perfil_permiso` cuelga de `codigo` y los usuarios lo referencian por código,
    por eso el código debe ser único (la DB es árbitro de la unicidad)."""
    __tablename__ = "perfiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(6), unique=True, index=True, default="")  # COD_PERFIL
    denominacion: Mapped[str] = mapped_column(String(60), default="")
    habilitado: Mapped[bool] = mapped_column(Boolean, default=True)


class UsuarioPerfil(Base):
    """Rol DIRECTO adicional de un usuario (multi-rol). El rol PRINCIPAL sigue en `usuarios.perfil`
    (lo usan JWT y el workflow); acá van los extra. Con vigencia opcional (licencias)."""
    __tablename__ = "usuario_perfil"
    __table_args__ = (UniqueConstraint("usuario_id", "perfil_codigo", name="uq_usuario_perfil"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    perfil_codigo: Mapped[str] = mapped_column(String(6), index=True)   # = rol
    vigente_desde: Mapped[date | None] = mapped_column(Date, nullable=True)
    vigente_hasta: Mapped[date | None] = mapped_column(Date, nullable=True)


class Grupo(Base):
    """Grupo = bundle de roles (p.ej. 'Área Créditos'). Un usuario miembro de un grupo hereda sus roles."""
    __tablename__ = "grupo"
    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    nombre: Mapped[str] = mapped_column(String(80), default="")
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class GrupoRol(Base):
    """Roles que contiene un grupo (grupo → rol). Relación estructural (sin vigencia)."""
    __tablename__ = "grupo_rol"
    __table_args__ = (UniqueConstraint("grupo_codigo", "rol_codigo", name="uq_grupo_rol"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    grupo_codigo: Mapped[str] = mapped_column(String(12), index=True)
    rol_codigo: Mapped[str] = mapped_column(String(6), index=True)


class UsuarioGrupo(Base):
    """Membresía de un usuario en un grupo, con vigencia opcional (enfermedad/vacaciones)."""
    __tablename__ = "usuario_grupo"
    __table_args__ = (UniqueConstraint("usuario_id", "grupo_codigo", name="uq_usuario_grupo"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    grupo_codigo: Mapped[str] = mapped_column(String(12), index=True)
    vigente_desde: Mapped[date | None] = mapped_column(Date, nullable=True)
    vigente_hasta: Mapped[date | None] = mapped_column(Date, nullable=True)


class UsuarioPermiso(Base):
    """Permiso DIRECTO de un usuario sobre una pantalla, con vigencia opcional (grant puntual)."""
    __tablename__ = "usuario_permiso"
    __table_args__ = (UniqueConstraint("usuario_id", "ruta", name="uq_usuario_permiso"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    ruta: Mapped[str] = mapped_column(String(80), index=True)
    nivel: Mapped[str] = mapped_column(String(10), default="CONSULTA")
    vigente_desde: Mapped[date | None] = mapped_column(Date, nullable=True)
    vigente_hasta: Mapped[date | None] = mapped_column(Date, nullable=True)


class PerfilPermiso(Base):
    """Permiso de un perfil sobre una pantalla (ruta del menú). Nivel de acceso:
    NINGUNO (sin acceso) | CONSULTA (lectura) | ESCRITURA (alta/edición) | TOTAL (incluye baja/admin).
    Sólo se guardan filas con nivel distinto de NINGUNO (ausencia = sin acceso)."""
    __tablename__ = "perfil_permiso"
    __table_args__ = (UniqueConstraint("perfil_codigo", "ruta", name="uq_perfil_permiso"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    perfil_codigo: Mapped[str] = mapped_column(String(6), index=True)
    ruta: Mapped[str] = mapped_column(String(80), index=True)   # p.ej. /creditos/configurar
    nivel: Mapped[str] = mapped_column(String(10), default="CONSULTA")


class Oficina(Base):
    """Oficina/dependencia interna (VFP: oficinas). Referenciada por los pases."""
    __tablename__ = "oficinas"

    id: Mapped[int] = mapped_column(primary_key=True)   # ID_OFICINA
    denominacion: Mapped[str] = mapped_column(String(60), default="")
    telefono_interno: Mapped[str] = mapped_column(String(10), default="")
    telefono_linea: Mapped[str] = mapped_column(String(20), default="")
    interna: Mapped[bool] = mapped_column(Boolean, default=True)


class TramitePase(Base):
    """Pase (movimiento de oficina) de un trámite de Mesa (VFP: pases, 428k).
    Ligado al trámite por tipo+letra+número+año. (Distinto de Pase de Expediente)."""
    __tablename__ = "tramite_pases"

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[str] = mapped_column(String(4), default="")
    letra: Mapped[str] = mapped_column(String(2), default="")
    numero: Mapped[int] = mapped_column(Integer, default=0)
    anio: Mapped[int] = mapped_column(Integer, default=0)
    fecha_pase: Mapped[date | None] = mapped_column(Date)
    oficina_origen: Mapped[int] = mapped_column(Integer, default=0)
    oficina_destino: Mapped[int] = mapped_column(Integer, default=0)
    texto: Mapped[str] = mapped_column(String(255), default="")
    activo: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (Index("ix_pase_tramite", "tipo", "letra", "numero", "anio"),)


class TipoTramite(Base):
    """Catálogo de tipos de trámite de Mesa de entradas (VFP: agjsmesa)."""
    __tablename__ = "tipos_tramite"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(60))
    prefijo: Mapped[str] = mapped_column(String(3), default="")  # p.ej. CR, PG
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class Turno(Base):
    """Turno de atención (VFP: agjsmesa — turnos)."""
    __tablename__ = "turnos"
    # Correlativo por día: unicidad (fecha, numero) garantizada por la DB. H-108.
    __table_args__ = (UniqueConstraint("fecha", "numero", name="uq_turnos_fecha_numero"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    numero: Mapped[int] = mapped_column(Integer, index=True)          # correlativo del día
    fecha: Mapped[date] = mapped_column(Date, index=True)
    tipo_tramite_id: Mapped[int] = mapped_column(ForeignKey("tipos_tramite.id"))
    cliente_nombre: Mapped[str] = mapped_column(String(80), default="")
    cliente_cuil: Mapped[str] = mapped_column(String(11), default="")
    estado: Mapped[str] = mapped_column(String(1), default="E")       # E espera, L llamado, A atendido, C cancelado
    box: Mapped[str] = mapped_column(String(20), default="")
    generado: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    atendido: Mapped[datetime | None] = mapped_column(DateTime)

    tipo_tramite: Mapped["TipoTramite"] = relationship()


class ModeloResolucion(Base):
    """Modelo/plantilla de resolución o disposición (VFP: rtf). Catálogo."""
    __tablename__ = "modelos_resolucion"

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo_res: Mapped[int] = mapped_column(Integer, default=0)          # TIPO_RES
    codigo: Mapped[int] = mapped_column(Integer, index=True, default=0)  # COD_MOD
    descripcion: Mapped[str] = mapped_column(String(120), default="")  # DES_MOD
    es_disposicion: Mapped[bool] = mapped_column(Boolean, default=False)  # DISPOSICIO
    es_seguros: Mapped[bool] = mapped_column(Boolean, default=False)   # SEGUROS
    tiene_plantilla: Mapped[bool] = mapped_column(Boolean, default=False)
    plantilla: Mapped[str] = mapped_column(Text, default="")           # MODELO (texto base que "Modelo a utilizar" carga)


class SolicitudCredito(Base):
    """Solicitud de crédito real (VFP: agjscreditos!solicitud). Base del Anexo de
    Resolución: se asignan a una resolución por lote. Reconstruido del fuente
    120100000anexo_res_dis (H-026)."""
    __tablename__ = "solicitudes_credito"

    id: Mapped[int] = mapped_column(primary_key=True)   # NO_SOLICIT
    fecha_soli: Mapped[date | None] = mapped_column(Date)
    cuil: Mapped[str] = mapped_column(String(11), index=True, default="")
    apellido_nombre: Mapped[str] = mapped_column(String(80), index=True, default="")
    dni: Mapped[str] = mapped_column(String(9), default="")
    montosol: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)   # capital
    no_credpp: Mapped[int] = mapped_column(Integer, default=0)
    importepp: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    linea: Mapped[int] = mapped_column(Integer, index=True, default=0)
    estado: Mapped[str] = mapped_column(String(2), index=True, default="")   # A aprobada…
    cubica: Mapped[str] = mapped_column(String(2), default="")               # C / DC / D
    no_resol: Mapped[int] = mapped_column(Integer, default=0, index=True)
    fecha_resol: Mapped[date | None] = mapped_column(Date)
    en_reso: Mapped[bool] = mapped_column(Boolean, default=False)
    lote: Mapped[int] = mapped_column(Integer, default=0, index=True)


class Resolucion(Base):
    """Resolución / Disposición administrativa (VFP: agjsdespacho — resoluciones)."""
    __tablename__ = "resoluciones"
    # Nº correlativo por año y tipo: unicidad (anio, tipo, numero) garantizada por la DB. H-108.
    __table_args__ = (UniqueConstraint("anio", "tipo", "numero", name="uq_resoluciones_anio_tipo_numero"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    numero: Mapped[int] = mapped_column(Integer, index=True)         # NRO_RES (Nº correlativo)
    anio: Mapped[int] = mapped_column(Integer, index=True)
    tipo: Mapped[str] = mapped_column(String(3), default="RES")      # RES / DIS
    fecha: Mapped[date] = mapped_column(Date)                        # FEC_RES
    # Nº Real / Fecha Real: el número OFICIAL, que se carga después del correlativo (pantalla VFP
    # "Carga Nº Real de RESOLUCIÓN"). Puede quedar nulo hasta que Despacho lo asigna. H-164.
    numero_real: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)   # NRO_REAL
    fecha_real: Mapped[date | None] = mapped_column(Date, nullable=True)                  # FEC_REAL
    organo: Mapped[str] = mapped_column(String(60), default="")
    asunto: Mapped[str] = mapped_column(String(200))
    motivo_cod: Mapped[int] = mapped_column(Integer, default=0)      # COD_MOT
    motivo: Mapped[str] = mapped_column(String(120), default="")     # etiqueta del motivo (ej. TRANSFERENCIA)
    importe: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)  # IMPORTE
    modelo_codigo: Mapped[int | None] = mapped_column(Integer, nullable=True)  # COD_MOD del modelo usado
    origen: Mapped[str] = mapped_column(String(40), default="")      # ID_TRAMITE/ID_LETRA/ID_NRO/ID_ANO (Exp./Nota origen)
    nro_op: Mapped[int | None] = mapped_column(Integer, nullable=True)   # NRO_OP (orden de pago asociada)
    texto: Mapped[str] = mapped_column(Text, default="")             # TEXTO (Texto del Instrumento Legal)
    estado: Mapped[str] = mapped_column(String(1), default="B")      # B borrador, F firmada
    anulada: Mapped[bool] = mapped_column(Boolean, default=False)    # LANULADA
    creado: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    beneficiarios: Mapped[list["ResolucionBeneficiario"]] = relationship(
        back_populates="resolucion", cascade="all, delete-orphan")


class ResolucionBeneficiario(Base):
    """Beneficiario de una resolución (VFP: Despacho/beneficiarios.dbf). Grilla al pie de la pantalla."""
    __tablename__ = "resolucion_beneficiarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    resolucion_id: Mapped[int] = mapped_column(ForeignKey("resoluciones.id"), index=True)
    tipo_doc: Mapped[int] = mapped_column(Integer, default=0)        # TIPO_DOC
    nro_doc: Mapped[str] = mapped_column(String(11), default="")     # NRO_DOC
    nombre: Mapped[str] = mapped_column(String(80), default="")      # NOMBRE
    tipo_bene: Mapped[int] = mapped_column(Integer, default=0)       # TIPO_BENE

    resolucion: Mapped["Resolucion"] = relationship(back_populates="beneficiarios")


class Expediente(Base):
    """Expediente / trámite que circula por pases (VFP: agjsdespacho / agjsmesa)."""
    __tablename__ = "expedientes"

    id: Mapped[int] = mapped_column(primary_key=True)
    numero: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    caratula: Mapped[str] = mapped_column(String(200))
    iniciador: Mapped[str] = mapped_column(String(80), default="")
    fecha_inicio: Mapped[date] = mapped_column(Date)
    estado: Mapped[str] = mapped_column(String(1), default="T")      # T en trámite, A archivado
    oficina_actual: Mapped[str] = mapped_column(String(60), default="")

    pases: Mapped[list["Pase"]] = relationship(
        back_populates="expediente", cascade="all, delete-orphan")


class Pase(Base):
    """Pase de un expediente entre oficinas (VFP: pases)."""
    __tablename__ = "pases"

    id: Mapped[int] = mapped_column(primary_key=True)
    expediente_id: Mapped[int] = mapped_column(ForeignKey("expedientes.id"), index=True)
    orden: Mapped[int] = mapped_column(Integer, default=1)
    fecha: Mapped[date] = mapped_column(Date)
    oficina_origen: Mapped[str] = mapped_column(String(60), default="")
    oficina_destino: Mapped[str] = mapped_column(String(60))
    motivo: Mapped[str] = mapped_column(String(200), default="")
    usuario: Mapped[str] = mapped_column(String(30), default="")

    expediente: Mapped["Expediente"] = relationship(back_populates="pases")


class OrdenPago(Base):
    """Orden de pago / egreso (VFP: agjsegresos — maeop, chequeras, OP)."""
    __tablename__ = "ordenes_pago"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Nº de OP generado (max+1 global): unicidad por la DB (árbitro) contra la carrera de dos procesos. H-108.
    numero: Mapped[int] = mapped_column(Integer, unique=True, index=True)   # no_op
    fecha: Mapped[date] = mapped_column(Date, index=True)
    beneficiario: Mapped[str] = mapped_column(String(80))
    cuit_beneficiario: Mapped[str] = mapped_column(String(11), default="")
    concepto: Mapped[str] = mapped_column(String(120))
    tipo: Mapped[str] = mapped_column(String(20), default="CREDITO")  # CREDITO/SEGURO/PROVEEDOR
    importe: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    iva: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)   # IVA del egreso
    estado: Mapped[str] = mapped_column(String(1), default="P")       # P pendiente, G girada, A anulada
    medio_pago: Mapped[str] = mapped_column(String(20), default="CHEQUE")
    banco: Mapped[str] = mapped_column(String(40), default="")
    cheque_numero: Mapped[str] = mapped_column(String(20), default="")
    fecha_pago: Mapped[date | None] = mapped_column(Date)
    credito_id: Mapped[int | None] = mapped_column(ForeignKey("creditos.id"))
    creado: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AutorizacionOP(Base):
    """Maestro de órdenes de pago = cupo autorizado (VFP: maeop, frm805100000altaop).
    Distinto de `OrdenPago` (el pago/egreso): una autorización con importe autorizado,
    importe usado y saldo, vigencia máxima y hasta 10 resoluciones que la respaldan.
    Los pagos consumen su saldo."""
    __tablename__ = "autorizaciones_op"

    id: Mapped[int] = mapped_column(primary_key=True)
    nop: Mapped[int] = mapped_column(Integer, index=True)              # NOP (n° por año)
    fecha: Mapped[date | None] = mapped_column(Date, index=True)       # FECHAOP
    vigencia: Mapped[date | None] = mapped_column(Date)               # FVIGENCIA
    importe: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)      # NIMPORTE autorizado
    importe_usado: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)  # NIMPUSA
    saldo: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)          # NSALDO
    sistema: Mapped[str] = mapped_column(String(20), default="")     # CSISTEMA/CSIS
    habilitada: Mapped[bool] = mapped_column(Boolean, default=True)   # LHABILITAD
    cancelada: Mapped[bool] = mapped_column(Boolean, default=False)   # LCANCELADA
    anulada: Mapped[bool] = mapped_column(Boolean, default=False)     # LANULA
    nres1: Mapped[int] = mapped_column(Integer, default=0)            # NRES1
    fres1: Mapped[date | None] = mapped_column(Date)                  # FRES1
    nres2: Mapped[int] = mapped_column(Integer, default=0)            # NRES2
    fres2: Mapped[date | None] = mapped_column(Date)                  # FRES2


class Chequera(Base):
    """Chequera de un banco (VFP: agjsegresos — chequeras, frm805050000altachequeras)."""
    __tablename__ = "chequeras"

    id: Mapped[int] = mapped_column(primary_key=True)
    banco: Mapped[str] = mapped_column(String(40))
    cuenta: Mapped[str] = mapped_column(String(30), default="")
    numero_desde: Mapped[int] = mapped_column(Integer)
    numero_hasta: Mapped[int] = mapped_column(Integer)
    proximo: Mapped[int] = mapped_column(Integer)          # próximo cheque a usar
    activa: Mapped[bool] = mapped_column(Boolean, default=True)


class MovimientoContable(Base):
    """Libro mayor real (VFP: agjscontable!asientos, 2M movimientos). Cada fila es un
    movimiento de una cuenta (débito o crédito) en una fecha/período, con referencia al
    comprobante. Fuente de los reportes contables sobre dato real (mayor, balance de
    sumas y saldos, IVA)."""
    __tablename__ = "movimientos_contables"

    id: Mapped[int] = mapped_column(primary_key=True)
    cuenta: Mapped[str] = mapped_column(String(20), index=True)       # CUENTA (código)
    ctaplan: Mapped[str] = mapped_column(String(20), default="")      # CTAPLAN
    fecha: Mapped[date | None] = mapped_column(Date, index=True)      # FECHA
    periodo: Mapped[str] = mapped_column(String(6), default="", index=True)  # CPERIO YYYYMM
    fecha_pago: Mapped[date | None] = mapped_column(Date)             # FECPAGO
    norden: Mapped[int] = mapped_column(Integer, default=0)           # NORDEN
    debito: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)   # NDEBITO
    credito: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)  # NCREDITO
    referencia: Mapped[str] = mapped_column(String(24), default="")   # CREFERENCI


class Empresa(Base):
    """Empresa / ente contable. Cada empresa tiene su propio plan de cuentas y sus propios libros
    (asientos, ejercicios). Habilita contabilidad separada por empresa (multi-plan). H-188."""
    __tablename__ = "empresas"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    nombre: Mapped[str] = mapped_column(String(80))
    cuit: Mapped[str] = mapped_column(String(13), default="")
    predeterminada: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    activa: Mapped[bool] = mapped_column(Boolean, default=True)
    creada_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class CuentaContable(Base):
    """Plan de cuentas (VFP: agjscontable). Scopeado por empresa: el código es único POR empresa."""
    __tablename__ = "cuentas_contables"
    __table_args__ = (UniqueConstraint("empresa_id", "codigo", name="uq_cuenta_empresa_codigo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int | None] = mapped_column(ForeignKey("empresas.id"), index=True, nullable=True)
    codigo: Mapped[str] = mapped_column(String(12), index=True)
    nombre: Mapped[str] = mapped_column(String(80))
    tipo: Mapped[str] = mapped_column(String(20))  # rubro: activo/pasivo/patrimonio/ingreso/egreso
    # Datos de la cuenta (pantalla Plan de cuentas moderna)
    descripcion: Mapped[str] = mapped_column(Text, default="")
    alias: Mapped[str] = mapped_column(String(40), default="")
    moneda: Mapped[str] = mapped_column(String(3), default="ARS")
    clasificacion: Mapped[str] = mapped_column(String(30), default="Sin clasificar")  # Caja/Banco/Cliente…
    saldo_normal: Mapped[str] = mapped_column(String(10), default="deudor")            # deudor|acreedor
    imputable: Mapped[bool] = mapped_column(Boolean, default=True)   # recibe asientos (hoja); grupo=False
    manual: Mapped[bool] = mapped_column(Boolean, default=False)     # admite carga manual
    entidades: Mapped[list] = mapped_column(JSON, default=list)      # [{tipo, entidad}] relacionadas


class CentroCosto(Base):
    """Centro de costo (dimensión analítica). Se puede asignar a cada línea de asiento para analizar
    resultados por área/negocio (Odoo: analytic accounting)."""
    __tablename__ = "centros_costo"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    nombre: Mapped[str] = mapped_column(String(60))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class ExtractoBancarioLinea(Base):
    """Línea del extracto bancario (resumen del banco) para la conciliación. Se coteja contra los
    movimientos del mayor en la cuenta banco. `importe` con signo: + aumenta el saldo del banco
    (crédito/depósito), − lo disminuye (débito/pago)."""
    __tablename__ = "extracto_bancario_lineas"

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int | None] = mapped_column(ForeignKey("empresas.id"), index=True, nullable=True)  # H-188
    cuenta_codigo: Mapped[str] = mapped_column(String(12), index=True)   # cuenta banco del plan (p.ej. 1.1.02)
    fecha: Mapped[date] = mapped_column(Date, index=True)
    descripcion: Mapped[str] = mapped_column(String(120), default="")
    referencia: Mapped[str] = mapped_column(String(40), default="")
    importe: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)   # con signo (+ ingreso / − egreso)
    conciliada: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    asiento_linea_id: Mapped[int | None] = mapped_column(ForeignKey("asientos_lineas.id"), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class EjercicioContable(Base):
    """Ejercicio contable (período fiscal). Estado abierto/cerrado; al cerrar se genera el asiento de
    cierre (refundición de resultados) y se bloquea la carga de asientos con fecha en el período."""
    __tablename__ = "ejercicios_contables"

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int | None] = mapped_column(ForeignKey("empresas.id"), index=True, nullable=True)  # H-188
    nombre: Mapped[str] = mapped_column(String(40))                 # ej. "Ejercicio 2026"
    fecha_desde: Mapped[date] = mapped_column(Date, index=True)
    fecha_hasta: Mapped[date] = mapped_column(Date, index=True)
    estado: Mapped[str] = mapped_column(String(10), default="abierto")   # abierto|cerrado
    resultado: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)  # resultado al cierre
    asiento_cierre_id: Mapped[int | None] = mapped_column(Integer)
    asiento_apertura_id: Mapped[int | None] = mapped_column(Integer)
    cerrado_en: Mapped[datetime | None] = mapped_column(DateTime)


class DiarioContable(Base):
    """Diario contable (Odoo: Journal). Agrupa los asientos por tipo de operación (Caja, Banco, Varios).
    Cada asiento pertenece a un diario."""
    __tablename__ = "diarios_contables"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(12), unique=True, index=True)   # CAJA, BANCO, VAR
    nombre: Mapped[str] = mapped_column(String(60))
    tipo: Mapped[str] = mapped_column(String(20), default="varios")            # caja/banco/varios
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class ImputacionContable(Base):
    """Parametrización contable: qué cuenta del plan imputa cada evento de una operación (otorgamiento,
    cobranza de capital/interés/IVA…). Reemplaza los códigos hardcodeados del motor de asientos por config
    editable. Se siembra con los códigos actuales (comportamiento sin cambios)."""
    __tablename__ = "imputaciones_contables"

    id: Mapped[int] = mapped_column(primary_key=True)
    clave: Mapped[str] = mapped_column(String(40), unique=True, index=True)   # ej. "cobranza_interes"
    grupo: Mapped[str] = mapped_column(String(40), default="")                # ej. "Cobranza de crédito"
    descripcion: Mapped[str] = mapped_column(String(80))                      # ej. "Intereses ganados (haber)"
    cuenta_codigo: Mapped[str] = mapped_column(String(12))                    # código del plan de cuentas


class CompaniaSeguros(Base):
    """Compañía aseguradora (VFP: agjsseguros)."""
    __tablename__ = "companias_seguros"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(80))
    cuit: Mapped[str] = mapped_column(String(11), default="")
    activa: Mapped[bool] = mapped_column(Boolean, default=True)


class Poliza(Base):
    """Póliza de seguro de vida sobre un crédito (VFP: cajacreseg / cresegu)."""
    __tablename__ = "polizas"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Nº de póliza generado (max+1 global): unicidad por la DB (árbitro). H-108.
    numero: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    credito_id: Mapped[int] = mapped_column(ForeignKey("creditos.id"), index=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id"), index=True)
    compania_id: Mapped[int] = mapped_column(ForeignKey("companias_seguros.id"))
    capital_asegurado: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    fecha_alta: Mapped[date] = mapped_column(Date)
    estado: Mapped[str] = mapped_column(String(1), default="V")  # V vigente, B baja

    compania: Mapped["CompaniaSeguros"] = relationship()


class TitularSeguro(Base):
    """Titular del seguro de vida colectivo (VFP: titulares, 122k)."""
    __tablename__ = "titulares_seguro"

    id: Mapped[int] = mapped_column(primary_key=True)
    cuil: Mapped[str] = mapped_column(String(11), index=True, default="")
    apellido_nombre: Mapped[str] = mapped_column(String(80), index=True, default="")
    tipo_titular: Mapped[str] = mapped_column(String(2), default="")   # A activo, etc.
    organo: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), default=0)
    sexo: Mapped[str] = mapped_column(String(1), default="")
    no_agente: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), default=0)
    fecha_nac: Mapped[date | None] = mapped_column(Date)
    domicilio: Mapped[str] = mapped_column(String(80), default="")
    localidad: Mapped[str] = mapped_column(String(40), default="")
    cantidad: Mapped[int] = mapped_column(Integer, default=1)


class Egreso(Base):
    """Transacción de egreso (VFP: Egresos/egresos.dbf, ~340 mil). Ledger real de
    pagos de Tesorería que respalda 'Busca transacciones de egresos' (81505).
    `sub_tipo` es el tipo de egreso mostrado; referencia a liquidación, resolución,
    crédito, OP, cheque y recibo. `anulado` = LANULADA."""
    __tablename__ = "egresos"

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo_egreso: Mapped[int] = mapped_column(Integer, default=0)
    sub_tipo: Mapped[int] = mapped_column(Integer, index=True, default=0)
    no_liquida: Mapped[int] = mapped_column(Integer, index=True, default=0)
    fecha_liqu: Mapped[date | None] = mapped_column(Date)
    tipo_res: Mapped[int] = mapped_column(Integer, default=0)
    nro_res: Mapped[int] = mapped_column(Integer, index=True, default=0)
    fec_res: Mapped[date | None] = mapped_column(Date)
    no_credito: Mapped[int] = mapped_column(Integer, index=True, default=0)
    no_solicit: Mapped[int] = mapped_column(Integer, default=0)
    apenom: Mapped[str] = mapped_column(String(40), index=True, default="")
    cuil: Mapped[str] = mapped_column(String(11), index=True, default="")
    no_op: Mapped[int] = mapped_column(Integer, index=True, default=0)
    fecha_op: Mapped[date | None] = mapped_column(Date, index=True)
    no_cheque: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), default=0)
    banco: Mapped[int] = mapped_column(Integer, default=0)
    no_recibo: Mapped[int] = mapped_column(Integer, index=True, default=0)
    no_cuota: Mapped[int] = mapped_column(Integer, default=0)
    importe: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    retenciones: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    fecha_pago: Mapped[date | None] = mapped_column(Date)
    pagado: Mapped[bool] = mapped_column(Boolean, default=False)
    anulado: Mapped[bool] = mapped_column(Boolean, default=False)


class ChequeEmitido(Base):
    """Cheque emitido por Tesorería (VFP: Egresos/cheques.dbf, ~73 mil). Respalda el
    'Listado de cheques emitidos en una fecha' (83040). `cuenta` es el tipo de
    chequera (CREDITOS/SEGUROS/JUEGOS/RENTAS); referencia a OP (nop/fop),
    resolución (nres/fres) y liquidación (nliqui). `anulado` = LANULA."""
    __tablename__ = "cheques_emitidos"

    id: Mapped[int] = mapped_column(primary_key=True)
    banco: Mapped[int] = mapped_column(Integer, index=True, default=0)          # NBANCO
    ncuenta: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), default=0)
    cuenta: Mapped[str] = mapped_column(String(20), index=True, default="")     # tipo de chequera
    ncheque: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), index=True, default=0)
    fecha: Mapped[date | None] = mapped_column(Date, index=True)
    importe: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    nop: Mapped[int] = mapped_column(Integer, default=0)                        # nº orden de pago
    fop: Mapped[date | None] = mapped_column(Date)
    nres: Mapped[int] = mapped_column(Integer, default=0)                       # nº resolución
    fres: Mapped[date | None] = mapped_column(Date)
    nliqui: Mapped[int] = mapped_column(Integer, default=0)                     # nº liquidación
    anulado: Mapped[bool] = mapped_column(Boolean, default=False)


class LiquidacionAgenciaHistorica(Base):
    """Liquidación de agencia de caja — HISTÓRICO (VFP: Caja/cj_liqhis.dbf, ~1,37M).
    Mismo detalle que `liquidaciones_agencia` (cajaliq vigente) pero archivado."""
    __tablename__ = "liquidaciones_agencia_hist"

    id: Mapped[int] = mapped_column(primary_key=True)
    cod_agencia: Mapped[int] = mapped_column(Integer, index=True, default=0)
    no_agencia: Mapped[int] = mapped_column(Integer, index=True, default=0)
    subagencia: Mapped[int] = mapped_column(Integer, default=0)
    cod_juego: Mapped[int] = mapped_column(Integer, index=True, default=0)
    juego: Mapped[str] = mapped_column(String(30), default="")
    no_sorteo: Mapped[int] = mapped_column(Integer, default=0)
    fecha_sorteo: Mapped[date | None] = mapped_column(Date, index=True)
    interior: Mapped[bool] = mapped_column(Boolean, default=False)
    moneda: Mapped[str] = mapped_column(String(4), default="")
    recaudacion: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    premios: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    com_premios: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    comision_agencia: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    comision_subagencia: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    multas: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    ing_brutos: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    fdo_gtia: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    intereses: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    iva: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    total_gral: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    fecha_vto: Mapped[date | None] = mapped_column(Date)
    pagado: Mapped[bool] = mapped_column(Boolean, default=False)
    fecha_pago: Mapped[date | None] = mapped_column(Date)
    cajero: Mapped[str] = mapped_column(String(20), default="")
    no_recibo: Mapped[int] = mapped_column(Integer, default=0)
    anulado: Mapped[bool] = mapped_column(Boolean, default=False)


class CajaPagoAgenciaHistorico(Base):
    """Pago de agencia de caja — HISTÓRICO (VFP: Caja/cj_paghis.dbf, ~652 mil).
    Mismo detalle que `caja_pagos_agencia` (cajapagos vigente) pero archivado."""
    __tablename__ = "caja_pagos_agencia_hist"

    id: Mapped[int] = mapped_column(primary_key=True)
    cod_agencia: Mapped[int] = mapped_column(Integer, index=True, default=0)
    fecha_pago: Mapped[date | None] = mapped_column(Date, index=True)
    origen: Mapped[str] = mapped_column(String(8), default="")
    no_recibo: Mapped[int] = mapped_column(Integer, default=0)
    bonos: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    pesos: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    cobrado_bonos: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    cobrado_pesos: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    cobrado_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    vuelto_bonos: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    vuelto_pesos: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    premios_bonos: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    premios_pesos: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    cajero: Mapped[str] = mapped_column(String(20), default="")
    anulado: Mapped[bool] = mapped_column(Boolean, default=False)


class CtaCteContableCredito(Base):
    """Cuenta corriente CONTABLE de créditos (VFP: Contabilidad/crctacte.dbf, ~1M).
    Detalle por crédito/cuota con el desglose contable completo: capital, interés
    normal/punitorio/resarcitorio, IVA, gastos, sellado, saldo. Más fino que
    `movimientos_cta` (ctacte.dbf)."""
    __tablename__ = "ctacte_contable_credito"

    id: Mapped[int] = mapped_column(primary_key=True)
    cuenta: Mapped[str] = mapped_column(String(12), index=True, default="")   # CUENTA (cartera)
    no_credito: Mapped[int] = mapped_column(Integer, index=True, default=0)
    no_cuota: Mapped[int] = mapped_column(Integer, default=0)
    corga: Mapped[str] = mapped_column(String(6), default="")
    fecha_vto: Mapped[date | None] = mapped_column(Date)
    fecha_pago: Mapped[date | None] = mapped_column(Date)
    via_pago: Mapped[str] = mapped_column(String(8), default="")
    cod_mov: Mapped[int] = mapped_column(Integer, default=0)
    signo: Mapped[int] = mapped_column(Integer, default=0)
    debitos: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    creditos: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    saldo: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    capital: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    int_normal: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    iva_normal: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    gastos: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    sellado: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    int_punit: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    iva_punit: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    int_resarc: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    iva_resarc: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    anulada: Mapped[bool] = mapped_column(Boolean, default=False)


class ContabilidadGeneral(Base):
    """Contabilidad general de caja/juegos por asiento (VFP: Contabilidad/contgral.dbf,
    ~106 mil). Un movimiento contable por recibo/asiento con importes por moneda
    (pesos, bonos, bono2, lecop)."""
    __tablename__ = "contabilidad_general"

    id: Mapped[int] = mapped_column(primary_key=True)
    fecha: Mapped[date | None] = mapped_column(Date, index=True)
    periodo: Mapped[str] = mapped_column(String(6), index=True, default="")   # NAAMM
    asiento: Mapped[int] = mapped_column(Integer, default=0)
    recibo: Mapped[int] = mapped_column(Integer, index=True, default=0)
    tipo: Mapped[str] = mapped_column(String(1), default="")     # I ingreso / E egreso
    agencia: Mapped[int] = mapped_column(Integer, default=0)
    subagencia: Mapped[int] = mapped_column(Integer, default=0)
    apellido_nombre: Mapped[str] = mapped_column(String(60), default="")
    destino: Mapped[str] = mapped_column(String(20), default="")
    origen: Mapped[str] = mapped_column(String(8), default="")
    sorteo: Mapped[int] = mapped_column(Integer, default=0)
    cuota: Mapped[int] = mapped_column(Integer, default=0)
    moneda: Mapped[str] = mapped_column(String(4), default="")
    total_pesos: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    total_bonos: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    total_bono2: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    total_lecop: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)


class CajaCreSegHistorico(Base):
    """Crédito/seguro cobrado en caja — HISTÓRICO (VFP: Caja/cj_crsghis.dbf, ~143 mil).
    Mismo detalle que `caja_creseg` (vigente) pero archivado."""
    __tablename__ = "caja_creseg_historico"

    id: Mapped[int] = mapped_column(primary_key=True)
    origen: Mapped[str] = mapped_column(String(8), default="")
    no_credito: Mapped[int] = mapped_column(Integer, index=True, default=0)
    cuil: Mapped[str] = mapped_column(String(11), index=True, default="")
    apellido_nombre: Mapped[str] = mapped_column(String(60), default="")
    cuota: Mapped[int] = mapped_column(Integer, default=0)
    interes: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    seguro: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    gastos: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    total_gral: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    moneda: Mapped[str] = mapped_column(String(4), default="")
    fecha_pago: Mapped[date | None] = mapped_column(Date, index=True)
    no_recibo: Mapped[int] = mapped_column(Integer, default=0)


class LiquidacionHistorica(Base):
    """Liquidación de agencia de juego histórica (VFP: Juegos/jghisliq.dbf,
    ~273 mil registros). Mismo esquema que las liquidaciones vigentes pero
    archivadas por el proceso 42515 (pasa liquidaciones a histórico). El informe
    de Fondo de Garantía (43025) une jghisliq + liquidaciones."""
    __tablename__ = "liquidaciones_historicas"

    id: Mapped[int] = mapped_column(primary_key=True)
    cod_agencia: Mapped[int] = mapped_column(Integer, index=True, default=0)
    no_agencia: Mapped[int] = mapped_column(Integer, index=True, default=0)
    subagencia: Mapped[int] = mapped_column(Integer, default=0)
    cod_juego: Mapped[int] = mapped_column(Integer, index=True, default=0)
    modalidad: Mapped[int] = mapped_column(Integer, default=0)
    no_sorteo: Mapped[int] = mapped_column(Integer, default=0)
    fecha: Mapped[date | None] = mapped_column(Date, index=True)
    interior: Mapped[bool] = mapped_column(Boolean, default=False)
    moneda: Mapped[str] = mapped_column(String(4), default="")
    recaudacion: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    premios: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    com_premios: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    multas: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    com_agencia: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    com_subagencia: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    fdo_gtia: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    ing_brutos: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)


class CtaCteSeguro(Base):
    """Cuenta corriente de seguros por agente (VFP: Seguros/ccseguros.dbf, ~180 mil).
    Un cargo de seguro por agente/período: importe del seguro `seguro` (tipo) en el
    `periodo`. Complementa la Visión 360 del cliente con su historial de seguros."""
    __tablename__ = "ctacte_seguros"

    id: Mapped[int] = mapped_column(primary_key=True)
    cuil: Mapped[str] = mapped_column(String(11), index=True, default="")
    no_agente: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), index=True, default=0)
    sexo: Mapped[str] = mapped_column(String(1), default="")
    periodo: Mapped[str] = mapped_column(String(6), index=True, default="")   # MMYYYY
    seguro: Mapped[int] = mapped_column(Integer, index=True, default=0)       # tipo de seguro
    importe: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    fecha_alta: Mapped[date | None] = mapped_column(Date)


class PolizaAgente(Base):
    """Póliza de seguro de vida colectivo por agente (VFP: Seguros/seguros.dbf,
    ~207 mil registros). `codigo` = tipo de seguro (paraseguros): 1 Subsidio
    Protección Familia, 2 Sepelio, 3 Vida Obligatorio, 4 Incapacidad, 5 s/def.
    ESTADO 'A' = activa/vigente. Es la fuente de 'Pólizas vigentes'."""
    __tablename__ = "polizas_agente"

    id: Mapped[int] = mapped_column(primary_key=True)          # CODIGO en origen? no: PK propia
    codigo: Mapped[int] = mapped_column(Integer, index=True, default=0)   # tipo de seguro
    no_poliza: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), index=True, default=0)
    cuil: Mapped[str] = mapped_column(String(11), index=True, default="")
    no_agente: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), index=True, default=0)
    sexo: Mapped[str] = mapped_column(String(1), default="")
    estado: Mapped[str] = mapped_column(String(2), index=True, default="A")  # A activa
    baja: Mapped[bool] = mapped_column(Boolean, default=False)
    cantidad: Mapped[int] = mapped_column(Integer, default=1)
    fecha: Mapped[date | None] = mapped_column(Date)
    fecha_alta: Mapped[date | None] = mapped_column(Date)


class SeguroAgente(Base):
    """Seguro del agente público por período (VFP: segurosap). Desglosa las
    coberturas: obligatorio, sepelio, cónyuge y adicional (seguro de vida)."""
    __tablename__ = "seguros_agente"

    id: Mapped[int] = mapped_column(primary_key=True)
    periodo: Mapped[str] = mapped_column(String(6), index=True)      # PERIODO MMYYYY
    cuil: Mapped[str] = mapped_column(String(11), index=True, default="")
    titular: Mapped[str] = mapped_column(String(60), default="")
    remuneracion: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    seg_obligatorio: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    seg_sepelio: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    seg_conyuge: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    seg_adicional: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)


class RegimenEspecial(Base):
    """Régimen especial de seguros/subsidios (VFP: agjsseguros — regímenes especiales).

    Ej.: Renta Vitalicia Héroes de Malvinas, Excombatientes, Subsidio de
    Protección a la Familia. `tipo` P = paga al beneficiario, C = cobra.
    """
    __tablename__ = "regimenes_especiales"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(80))
    tipo: Mapped[str] = mapped_column(String(1), default="P")   # P paga, C cobra
    monto_default: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class Beneficiario(Base):
    """Beneficiario de un régimen especial (VFP: maetit / beneficiarios)."""
    __tablename__ = "beneficiarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    regimen_id: Mapped[int] = mapped_column(ForeignKey("regimenes_especiales.id"), index=True)
    apellido_nombre: Mapped[str] = mapped_column(String(80))
    cuil: Mapped[str] = mapped_column(String(11), default="")
    dni: Mapped[str] = mapped_column(String(9), default="")
    cbu: Mapped[str] = mapped_column(String(23), default="")
    monto_mensual: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    numero_resolucion: Mapped[str] = mapped_column(String(20), default="")
    fecha_alta: Mapped[date] = mapped_column(Date)
    estado: Mapped[str] = mapped_column(String(1), default="V")  # V vigente, B baja

    regimen: Mapped["RegimenEspecial"] = relationship()


class CuotaRegimen(Base):
    """Cuota mensual de un beneficiario de régimen especial."""
    __tablename__ = "cuotas_regimen"

    id: Mapped[int] = mapped_column(primary_key=True)
    beneficiario_id: Mapped[int] = mapped_column(ForeignKey("beneficiarios.id"), index=True)
    regimen_id: Mapped[int] = mapped_column(ForeignKey("regimenes_especiales.id"), index=True)
    periodo: Mapped[str] = mapped_column(String(7), index=True)   # YYYY-MM
    monto: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    estado: Mapped[str] = mapped_column(String(1), default="G")   # G generada, L liquidada
    orden_pago_id: Mapped[int | None] = mapped_column(ForeignKey("ordenes_pago.id"))
    generado: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Asiento(Base):
    """Asiento contable (cabecera). VFP: cb-crasientootorga / cb-crasientodevenga."""
    __tablename__ = "asientos"

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int | None] = mapped_column(ForeignKey("empresas.id"), index=True, nullable=True)  # H-188
    fecha: Mapped[date] = mapped_column(Date, index=True)
    concepto: Mapped[str] = mapped_column(String(120))
    origen: Mapped[str] = mapped_column(String(20), index=True)  # otorgamiento/cobranza/pp_*/legacy/manual/reversa
    ref_id: Mapped[int | None] = mapped_column(Integer)  # id de crédito/recibo
    creado: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    # Asientos MANUALES (contabilidad general): correlativo por año, reversa y auditoría.
    numero: Mapped[int | None] = mapped_column(Integer, index=True)   # correlativo por año (sólo manuales)
    reversado: Mapped[bool] = mapped_column(Boolean, default=False)   # ya tiene su contra-asiento
    reversa_de: Mapped[int | None] = mapped_column(Integer)           # id del asiento original si es una reversa
    usuario: Mapped[str] = mapped_column(String(30), default="")
    estado: Mapped[str] = mapped_column(String(12), default="publicado", index=True)  # borrador|publicado
    diario_codigo: Mapped[str] = mapped_column(String(12), default="")               # diario (Odoo journal)

    lineas: Mapped[list["AsientoLinea"]] = relationship(
        back_populates="asiento", cascade="all, delete-orphan")


class AsientoLinea(Base):
    __tablename__ = "asientos_lineas"

    id: Mapped[int] = mapped_column(primary_key=True)
    asiento_id: Mapped[int] = mapped_column(ForeignKey("asientos.id"), index=True)
    cuenta_codigo: Mapped[str] = mapped_column(String(12))
    cuenta_nombre: Mapped[str] = mapped_column(String(80))
    debe: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    haber: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    centro_codigo: Mapped[str] = mapped_column(String(12), default="")   # centro de costo (analítica)

    asiento: Mapped["Asiento"] = relationship(back_populates="lineas")


def _empresa_pred_id(connection):
    """id de la empresa predeterminada (para defaultear empresa_id en cuentas/asientos). H-188."""
    try:
        row = connection.exec_driver_sql(
            "SELECT id FROM empresas WHERE predeterminada = %s ORDER BY id LIMIT 1"
            if connection.dialect.name != "sqlite" else
            "SELECT id FROM empresas WHERE predeterminada = 1 ORDER BY id LIMIT 1",
            (True,) if connection.dialect.name != "sqlite" else ()).first()
        return row[0] if row else None
    except Exception:
        return None


@event.listens_for(CuentaContable, "before_insert")
def _cuenta_empresa_default(mapper, connection, target):
    """Si no se indicó empresa, la cuenta va a la empresa predeterminada (contabilidad por empresa). H-188."""
    if target.empresa_id is None:
        target.empresa_id = _empresa_pred_id(connection)


@event.listens_for(Asiento, "before_insert")
def _asiento_empresa_default(mapper, connection, target):
    """Si no se indicó empresa, el asiento va a los libros de la empresa predeterminada. H-188."""
    if target.empresa_id is None:
        target.empresa_id = _empresa_pred_id(connection)


@event.listens_for(Asiento, "before_insert")
def _asiento_balanceado(mapper, connection, target):
    """Guarda mecánica del principio 'contabilidad balanceada': todo asiento de la app (doble partida)
    debe cumplir Σdebe = Σhaber. Los asientos migrados del mayor plano de VFP (origen='legacy') son de
    una sola pierna por naturaleza y se excluyen. Un asiento desbalanceado falla ruidoso, no en silencio."""
    if (target.origen or "").lower() == "legacy":
        return
    from decimal import Decimal as _D
    d = sum((l.debe or _D(0) for l in target.lineas), _D(0))
    h = sum((l.haber or _D(0) for l in target.lineas), _D(0))
    if d != h:
        raise ValueError(
            f"Asiento desbalanceado (origen={target.origen!r}, concepto={target.concepto!r}): "
            f"Σdebe={d} ≠ Σhaber={h}. Todo asiento de la app debe balancear (contabilidad balanceada).")


class Impuesto(Base):
    """Maestro de impuestos del sistema (IVA, IIBB, sellado, percepciones…).

    General: cualquier módulo (créditos, seguros, tesorería) puede referenciarlo.
    Se administra desde Contabilidad → Impuestos.
    """
    __tablename__ = "impuestos"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True, index=True)  # IVA21, IIBB...
    nombre: Mapped[str] = mapped_column(String(120))
    tipo: Mapped[str] = mapped_column(String(20), default="IVA")   # IVA, IIBB, SELLADO, PERCEPCION, RETENCION, OTRO
    alicuota: Mapped[Decimal] = mapped_column(Numeric(9, 4), default=0)  # %
    base: Mapped[str] = mapped_column(String(20), default="INTERES")     # INTERES, CARGOS, CUOTA, CAPITAL, TOTAL
    cuenta_contable: Mapped[str] = mapped_column(String(12), default="")
    jurisdiccion: Mapped[str] = mapped_column(String(40), default="")     # para IIBB
    vigente_desde: Mapped[date | None] = mapped_column(Date, nullable=True)
    vigente_hasta: Mapped[date | None] = mapped_column(Date, nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class IndiceReferencia(Base):
    """Índices de referencia para tasas variables (BADLAR, política monetaria, UVA…).

    Maestro general del sistema (Contabilidad → Índices). La tasa efectiva de un producto de
    tasa variable = valor del índice + margen.
    """
    __tablename__ = "indices_referencia"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    nombre: Mapped[str] = mapped_column(String(120))
    valor: Mapped[Decimal] = mapped_column(Numeric(9, 4), default=0)   # % nominal anual vigente
    fuente: Mapped[str] = mapped_column(String(60), default="")        # BCRA, INDEC...
    fecha_valor: Mapped[date | None] = mapped_column(Date, nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class Feriado(Base):
    """Maestro de feriados por país (calendario de días no laborables).

    Lo usa el motor de cronograma para no fechar vencimientos en días inhábiles cuando el
    producto ajusta a día hábil. Se puede cargar manualmente o importar de una fuente oficial.
    tipo: INAMOVIBLE (fecha fija) · TRASLADABLE · PUENTE · NO_LABORABLE.
    origen: MANUAL · OFICIAL (importado de una fuente).
    """
    __tablename__ = "feriados"
    __table_args__ = (UniqueConstraint("pais", "fecha", name="uq_feriado_pais_fecha"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    pais: Mapped[str] = mapped_column(String(2), index=True, default="AR")  # ISO-3166 alpha-2
    fecha: Mapped[date] = mapped_column(Date, index=True)
    nombre: Mapped[str] = mapped_column(String(120))
    tipo: Mapped[str] = mapped_column(String(20), default="INAMOVIBLE")
    origen: Mapped[str] = mapped_column(String(10), default="MANUAL")
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
