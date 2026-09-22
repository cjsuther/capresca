"""Consultas e informes del módulo Créditos (read-only)."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import get_current_user
from app.services import consultas as svc
from app.reports.excel import (envios_excel, listado_creditos_excel,
                               pagos_caja_excel, turnos_excel)
from app.reports.pdf import cartera_pdf, por_cartera_pdf
from app import schemas

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

router = APIRouter(prefix="/api/creditos/creditos/consultas", tags=["creditos-consultas"],
                   dependencies=[Depends(get_current_user)])


@router.get("/cliente/{cliente_id}/situacion", response_model=schemas.SituacionCliente)
def situacion(cliente_id: int, db: Session = Depends(get_db)):
    data = svc.situacion_cliente(db, cliente_id)
    if not data:
        raise HTTPException(404, "Cliente no encontrado")
    return data


@router.get("/estadisticas", response_model=schemas.EstadisticasCartera)
def estadisticas(db: Session = Depends(get_db)):
    return svc.estadisticas_cartera(db)


@router.get("/creditos")
def listado_creditos(
    estado: str | None = None,
    q: str | None = None,
    linea_id: int | None = None,
    cartera: int | None = None,
    organismo_id: int | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    con_saldo: bool | None = None,
    limit: int = 25,
    offset: int = 0,
    sort: str = "credito_id",
    order: str = "desc",
    db: Session = Depends(get_db),
):
    """Informe de créditos con filtros combinables (estado, línea, cartera,
    organismo, fechas, saldo) — VFP: 330 / 33085 Informes varios."""
    return svc.listado_creditos(db, estado, q=q, linea_id=linea_id, cartera=cartera,
                                organismo_id=organismo_id, desde=desde, hasta=hasta,
                                con_saldo=con_saldo, limit=limit, offset=offset,
                                sort=sort, order=order)


@router.get("/creditos/excel")
def listado_creditos_excel_endpoint(
    estado: str | None = None, q: str | None = None,
    linea_id: int | None = None, cartera: int | None = None,
    organismo_id: int | None = None, desde: date | None = None, hasta: date | None = None,
    con_saldo: bool | None = None,
    sort: str = "credito_id", order: str = "desc", db: Session = Depends(get_db),
):
    """Exporta el informe de créditos filtrado (set completo) a Excel."""
    data = svc.listado_creditos(db, estado, q=q, linea_id=linea_id, cartera=cartera,
                                organismo_id=organismo_id, desde=desde, hasta=hasta,
                                con_saldo=con_saldo, limit=100000, offset=0,
                                sort=sort, order=order, cap=100000)
    xlsx = listado_creditos_excel(data["items"])
    return Response(content=xlsx, media_type=XLSX, headers={
        "Content-Disposition": 'attachment; filename="informe_creditos.xlsx"'})


@router.get("/cuotas-mora")
def cuotas_mora(fecha_corte: date, db: Session = Depends(get_db)):
    return svc.cuotas_en_mora(db, fecha_corte)


@router.get("/por-cartera")
def situacion_por_cartera(db: Session = Depends(get_db)):
    """Cantidades y situación de créditos por cartera (VFP: 31537)."""
    return svc.situacion_por_cartera(db)


@router.get("/por-cartera/pdf")
def por_cartera_pdf_endpoint(db: Session = Depends(get_db)):
    """Resumen ejecutivo de créditos por cartera en PDF."""
    pdf = por_cartera_pdf(svc.situacion_por_cartera(db))
    return Response(content=pdf, media_type="application/pdf", headers={
        "Content-Disposition": 'inline; filename="creditos_por_cartera.pdf"'})


@router.get("/turnos")
def turnos_otorgados(
    periodo: str | None = None, tipo: str | None = None, usado: bool | None = None,
    q: str | None = None, limit: int = 25, offset: int = 0,
    db: Session = Depends(get_db),
):
    """Turnos otorgados para solicitar crédito (VFP: 31560)."""
    return svc.turnos_otorgados(db, periodo=periodo, tipo=tipo, usado=usado,
                                q=q, limit=limit, offset=offset)


@router.get("/turnos/excel")
def turnos_excel_endpoint(
    periodo: str | None = None, tipo: str | None = None, usado: bool | None = None,
    q: str | None = None, db: Session = Depends(get_db),
):
    """Exporta los turnos otorgados filtrados (set completo) a Excel."""
    data = svc.turnos_otorgados(db, periodo=periodo, tipo=tipo, usado=usado, q=q,
                                limit=200000, offset=0, cap=200000)
    xlsx = turnos_excel(data["items"])
    return Response(content=xlsx, media_type=XLSX, headers={
        "Content-Disposition": 'attachment; filename="turnos_otorgados.xlsx"'})


@router.get("/sin-debito")
def creditos_sin_debito(q: str | None = None, linea_id: int | None = None,
                        limit: int = 25, offset: int = 0, db: Session = Depends(get_db)):
    """Créditos activos sin CBU (sin débito automático). Con linea_id filtra por
    línea (variante 'de Línea 25') — VFP: solsindeb / solsindeb25."""
    return svc.creditos_sin_debito(db, q=q, linea_id=linea_id, limit=limit, offset=offset)


@router.get("/pagos-caja")
def pagos_en_caja(
    desde: date | None = None, hasta: date | None = None,
    credito_id: int | None = None, via: str | None = None,
    limit: int = 25, offset: int = 0, db: Session = Depends(get_db),
):
    """Pagos de créditos registrados en caja (VFP: frm315550000pagcrecaja)."""
    return svc.pagos_en_caja(db, desde=desde, hasta=hasta, credito_id=credito_id,
                             via=via, limit=limit, offset=offset)


@router.get("/pagos-caja/excel")
def pagos_caja_excel_endpoint(
    desde: date | None = None, hasta: date | None = None,
    credito_id: int | None = None, via: str | None = None,
    db: Session = Depends(get_db),
):
    """Exporta los pagos en caja filtrados (set completo) a Excel."""
    data = svc.pagos_en_caja(db, desde=desde, hasta=hasta, credito_id=credito_id,
                             via=via, limit=200000, offset=0, cap=200000)
    xlsx = pagos_caja_excel(data["items"])
    return Response(content=xlsx, media_type=XLSX, headers={
        "Content-Disposition": 'attachment; filename="pagos_en_caja.xlsx"'})


@router.get("/cuenta-corriente/{credito_id}")
def cuenta_corriente(credito_id: int, db: Session = Depends(get_db)):
    """Cuenta corriente (movimientos débito/crédito) de un crédito."""
    return svc.cuenta_corriente(db, credito_id)


# ---------------- Jubilados / Ley 5094 ----------------
@router.get("/jubilados/resumen")
def jubilados_resumen(db: Session = Depends(get_db)):
    from app.services import jubilados as jsvc
    return jsvc.resumen(db)


@router.get("/jubilados/por-departamento")
def jubilados_por_depto(db: Session = Depends(get_db)):
    from app.services import jubilados as jsvc
    return jsvc.por_departamento(db)


@router.get("/envios", response_model=schemas.EnviosResumen)
def envios(desde: date, hasta: date, db: Session = Depends(get_db)):
    return svc.envios(db, desde, hasta)


@router.get("/estadisticas/pdf")
def estadisticas_pdf(db: Session = Depends(get_db)):
    """Informe de cartera de créditos por línea (PDF)."""
    data = svc.estadisticas_cartera(db)
    pdf = cartera_pdf(data)
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": 'inline; filename="cartera.pdf"'})


@router.get("/envios/excel")
def envios_excel_endpoint(desde: date, hasta: date, db: Session = Depends(get_db)):
    """Padrón de débito por planilla en Excel (para el banco)."""
    data = svc.envios(db, desde, hasta)
    xlsx = envios_excel(data)
    return Response(content=xlsx, media_type=XLSX, headers={
        "Content-Disposition": f'attachment; filename="padron_debito_{desde}_{hasta}.xlsx"'})


@router.get("/resumen-cobros")
def resumen_cobros(desde: date | None = None, hasta: date | None = None,
                   db: Session = Depends(get_db)):
    """Resumen de cobros de créditos por período mensual (VFP: frm330150000rptcobcre)."""
    return svc.resumen_cobros_creditos(db, desde=desde, hasta=hasta)
