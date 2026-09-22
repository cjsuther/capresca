"""Contabilidad: plan de cuentas, ejercicios, definiciones de asiento, transacciones y asientos.

Regla de oro del módulo: **ningún módulo manda asientos**. Los módulos mandan la TRANSACCIÓN que
ocurrió (un desembolso, una cobranza, un pago) y acá se decide cómo se contabiliza, con la
`DefinicionAsiento` de ese tipo de transacción. Si no hay definición, la transacción queda
PENDIENTE_CONFIGURACION: nada se inventa ni se pierde, y cuando se define la regla se procesa.

Así la trazabilidad es completa en los dos sentidos: de la transacción al asiento y del asiento a la
operación que lo originó.
"""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text,
                        UniqueConstraint, func)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base

JSONTipo = JSON().with_variant(JSONB, "postgresql")

# Rubros del plan de cuentas (los cinco de siempre + cuentas de orden).
RUBROS = ("ACTIVO", "PASIVO", "PATRIMONIO", "INGRESO", "EGRESO", "ORDEN")
# Los dos primeros son patrimoniales: sus saldos pasan al ejercicio siguiente.
PATRIMONIALES = ("ACTIVO", "PASIVO", "PATRIMONIO")
RESULTADO = ("INGRESO", "EGRESO")

ESTADOS_TRANSACCION = ("PENDIENTE_CONFIGURACION", "CONTABILIZADA", "ERROR", "ANULADA")
ESTADOS_ASIENTO = ("BORRADOR", "REGISTRADO", "ANULADO")
ORIGENES_ASIENTO = ("TRANSACCION", "MANUAL", "APERTURA", "CIERRE", "REVERSA")


class Empresa(Base):
    """Ente contable. En Argentina el CUIT y la condición frente al IVA son parte de los libros."""
    __tablename__ = "empresas"

    id: Mapped[int] = mapped_column(primary_key=True)
    razon_social: Mapped[str] = mapped_column(String(120))
    cuit: Mapped[str] = mapped_column(String(11), default="")
    condicion_iva: Mapped[str] = mapped_column(String(30), default="RESPONSABLE_INSCRIPTO")
    domicilio: Mapped[str] = mapped_column(String(160), default="")
    inicio_actividades: Mapped[date | None] = mapped_column(Date, nullable=True)
    predeterminada: Mapped[bool] = mapped_column(Boolean, default=True)


class Cuenta(Base):
    """Cuenta del plan. `imputable=False` = cuenta de agrupación (no recibe asientos)."""
    __tablename__ = "cuentas"
    __table_args__ = (UniqueConstraint("codigo", name="uq_cuenta_codigo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), index=True)          # 1.1.01.001
    nombre: Mapped[str] = mapped_column(String(120))
    rubro: Mapped[str] = mapped_column(String(15), index=True)
    imputable: Mapped[bool] = mapped_column(Boolean, default=True)
    saldo_normal: Mapped[str] = mapped_column(String(10), default="DEUDOR")   # DEUDOR | ACREEDOR
    moneda: Mapped[str] = mapped_column(String(3), default="ARS")
    # Ajuste por inflación (RT 6): qué cuentas se ajustan (no monetarias) y cuáles no.
    ajustable: Mapped[bool] = mapped_column(Boolean, default=False)
    requiere_centro: Mapped[bool] = mapped_column(Boolean, default=False)
    descripcion: Mapped[str] = mapped_column(String(300), default="")
    activa: Mapped[bool] = mapped_column(Boolean, default=True)


class CentroCosto(Base):
    __tablename__ = "centros_costo"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    nombre: Mapped[str] = mapped_column(String(80))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class Diario(Base):
    """Agrupa los asientos por tipo de operación (Caja, Banco, Ventas, Compras, Varios) y les da su
    numeración correlativa dentro del ejercicio."""
    __tablename__ = "diarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    nombre: Mapped[str] = mapped_column(String(60))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class Ejercicio(Base):
    """Ejercicio contable. Un asiento sólo entra en un ejercicio ABIERTO."""
    __tablename__ = "ejercicios"

    id: Mapped[int] = mapped_column(primary_key=True)
    numero: Mapped[int] = mapped_column(Integer, unique=True)             # 2026
    desde: Mapped[date] = mapped_column(Date)
    hasta: Mapped[date] = mapped_column(Date)
    estado: Mapped[str] = mapped_column(String(10), default="ABIERTO", index=True)   # ABIERTO | CERRADO
    cerrado_por: Mapped[str] = mapped_column(String(60), default="")
    cerrado_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Cuenta a la que se refunden los resultados al cerrar (Resultado del ejercicio).
    cuenta_resultado: Mapped[str] = mapped_column(String(20), default="")


class DefinicionAsiento(Base):
    """Cómo se contabiliza un tipo de transacción de un módulo. Sin esto, la transacción espera.

    `lineas`: [{cuenta, dc: "DEBE"|"HABER", importe: "<expresión sobre los datos>", centro, detalle,
                omitir_si_cero}]
    La expresión usa los campos que manda el módulo: "capital + interes", "iva", "total * 0.21"…
    """
    __tablename__ = "definiciones_asiento"
    __table_args__ = (UniqueConstraint("modulo", "tipo", "vigente_desde", name="uq_definicion_vigencia"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    modulo: Mapped[str] = mapped_column(String(30), index=True)
    tipo: Mapped[str] = mapped_column(String(60), index=True)             # DESEMBOLSO, COBRANZA_CUOTA…
    nombre: Mapped[str] = mapped_column(String(120))
    diario_codigo: Mapped[str] = mapped_column(String(12), default="VAR")
    leyenda: Mapped[str] = mapped_column(String(200), default="")         # plantilla: "Desembolso {referencia}"
    lineas: Mapped[list] = mapped_column(JSONTipo, default=list)
    vigente_desde: Mapped[date | None] = mapped_column(Date, nullable=True)
    vigente_hasta: Mapped[date | None] = mapped_column(Date, nullable=True)
    activa: Mapped[bool] = mapped_column(Boolean, default=True)
    creada_por: Mapped[str] = mapped_column(String(60), default="")
    creada_en: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Transaccion(Base):
    """Lo que pasó en un módulo, tal como lo mandó. Es la fuente del asiento y su trazabilidad."""
    __tablename__ = "transacciones"
    __table_args__ = (UniqueConstraint("modulo", "tipo", "referencia", name="uq_transaccion_referencia"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    modulo: Mapped[str] = mapped_column(String(30), index=True)
    tipo: Mapped[str] = mapped_column(String(60), index=True)
    referencia: Mapped[str] = mapped_column(String(80), index=True)        # id/numero del módulo
    fecha: Mapped[date] = mapped_column(Date, index=True)
    moneda: Mapped[str] = mapped_column(String(3), default="ARS")
    descripcion: Mapped[str] = mapped_column(String(200), default="")
    datos: Mapped[dict] = mapped_column(JSONTipo, default=dict)            # importes y campos del evento
    estado: Mapped[str] = mapped_column(String(25), default="PENDIENTE_CONFIGURACION", index=True)
    motivo: Mapped[str] = mapped_column(String(300), default="")           # por qué no se contabilizó
    asiento_id: Mapped[int | None] = mapped_column(ForeignKey("asientos.id"), nullable=True)
    usuario_origen: Mapped[str] = mapped_column(String(60), default="")
    recibida_en: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    procesada_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    asiento: Mapped["Asiento"] = relationship(foreign_keys=[asiento_id])


class Asiento(Base):
    """Asiento contable. No se edita ni se borra: se anula con su contra-asiento (reversa)."""
    __tablename__ = "asientos"
    __table_args__ = (UniqueConstraint("ejercicio_id", "numero", name="uq_asiento_numero_ejercicio"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    ejercicio_id: Mapped[int] = mapped_column(ForeignKey("ejercicios.id"), index=True)
    numero: Mapped[int] = mapped_column(Integer)                           # correlativo por ejercicio
    fecha: Mapped[date] = mapped_column(Date, index=True)
    diario_codigo: Mapped[str] = mapped_column(String(12), default="VAR", index=True)
    concepto: Mapped[str] = mapped_column(String(200), default="")
    estado: Mapped[str] = mapped_column(String(12), default="REGISTRADO", index=True)
    origen: Mapped[str] = mapped_column(String(15), default="TRANSACCION", index=True)
    transaccion_id: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    definicion_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reversa_de: Mapped[int | None] = mapped_column(Integer, nullable=True)
    anulado_por_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    usuario: Mapped[str] = mapped_column(String(60), default="")
    creado_en: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    lineas: Mapped[list["AsientoLinea"]] = relationship(back_populates="asiento", cascade="all, delete-orphan",
                                                        order_by="AsientoLinea.id")


class AsientoLinea(Base):
    __tablename__ = "asientos_lineas"

    id: Mapped[int] = mapped_column(primary_key=True)
    asiento_id: Mapped[int] = mapped_column(ForeignKey("asientos.id", ondelete="CASCADE"), index=True)
    cuenta_codigo: Mapped[str] = mapped_column(String(20), index=True)
    cuenta_nombre: Mapped[str] = mapped_column(String(120), default="")
    debe: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    haber: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    centro_codigo: Mapped[str] = mapped_column(String(12), default="")
    detalle: Mapped[str] = mapped_column(String(200), default="")
    asiento: Mapped[Asiento] = relationship(back_populates="lineas")


class ComprobanteIva(Base):
    """Libro IVA Ventas / Compras: lo que la transacción declara como comprobante fiscal.

    El módulo manda los datos del comprobante (tipo, punto de venta, número, CUIT, netos e IVA) junto
    con la transacción; acá se asientan y además se registran para el libro.
    """
    __tablename__ = "comprobantes_iva"
    __table_args__ = (UniqueConstraint("libro", "tipo_comprobante", "punto_venta", "numero", "cuit",
                                       name="uq_comprobante_iva"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    libro: Mapped[str] = mapped_column(String(8), index=True)              # VENTAS | COMPRAS
    fecha: Mapped[date] = mapped_column(Date, index=True)
    tipo_comprobante: Mapped[str] = mapped_column(String(4), default="01")  # 01 Factura A, 06 Factura B…
    punto_venta: Mapped[int] = mapped_column(Integer, default=0)
    numero: Mapped[int] = mapped_column(Integer, default=0)
    cuit: Mapped[str] = mapped_column(String(11), default="")
    razon_social: Mapped[str] = mapped_column(String(120), default="")
    condicion_iva: Mapped[str] = mapped_column(String(30), default="")
    neto_gravado: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    neto_no_gravado: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    exento: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    alicuota: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("21"))
    iva: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    percepciones: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    retenciones: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    transaccion_id: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    asiento_id: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    detalle: Mapped[str] = mapped_column(Text, default="")


class LineaExtracto(Base):
    """Línea del extracto del banco, para conciliar contra el mayor de la cuenta bancaria.

    `asiento_linea_id` es el movimiento contable con el que quedó conciliada (None = pendiente).
    """
    __tablename__ = "extracto_bancario"

    id: Mapped[int] = mapped_column(primary_key=True)
    cuenta_codigo: Mapped[str] = mapped_column(String(20), index=True)
    fecha: Mapped[date] = mapped_column(Date, index=True)
    descripcion: Mapped[str] = mapped_column(String(200), default="")
    referencia: Mapped[str] = mapped_column(String(80), default="")
    importe: Mapped[Decimal] = mapped_column(Numeric(16, 2))      # + entrada / − salida, como el banco
    asiento_linea_id: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    conciliada_por: Mapped[str] = mapped_column(String(60), default="")
    conciliada_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    creada_en: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

