"""ETL: carga los MAESTROS reales (organismos, líneas, clientes) desde los DBF
del backup a la base del sistema nuevo.

Uso:
    DATABASE_URL=sqlite+pysqlite:///./ccypp_real.db \
    python3 -m app.etl.cargar_maestros "/ruta/a/bases"
"""
from __future__ import annotations

import os
import sys
from decimal import Decimal, InvalidOperation

from app.core.database import Base, engine, SessionLocal
from app.etl.dbf import DbfReader
from app.core.security import hash_password
from app import models


def D(v, default="0"):
    try:
        return Decimal(str(v)) if v not in (None, "") else Decimal(default)
    except (InvalidOperation, ValueError):
        return Decimal(default)


def I(v, default=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def S(v):
    return (str(v).strip() if v is not None else "")


def cargar(bases: str):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # Usuario admin para poder entrar
    if not db.query(models.Usuario).filter_by(username="admin").first():
        db.add(models.Usuario(username="admin", nombre="Administrador",
                              password_hash=hash_password("admin123"), perfil="ADMG"))
        db.commit()

    # Config (regímenes especiales, tipos de trámite, plan de cuentas)
    from app.seed import seed_config
    seed_config(db)

    # ---------------- Organismos (General/organismos) ----------------
    p = os.path.join(bases, "General", "organismos.dbf")
    if os.path.exists(p) and not db.query(models.Organismo).first():
        rows = []
        with DbfReader(p) as r:
            for x in r.records():
                x = {k.lower(): v for k, v in x.items()}
                oid = I(x.get("organo"))
                if not oid:
                    continue
                rows.append({"id": oid, "codigo": str(oid),
                             "nombre": S(x.get("nombre"))[:120], "activo": True})
        # dedup por id
        vistos, limpios = set(), []
        for row in rows:
            if row["id"] in vistos:
                continue
            vistos.add(row["id"]); limpios.append(row)
        db.bulk_insert_mappings(models.Organismo, limpios)
        db.commit()
        print(f"  organismos: {len(limpios)}")

    org_ids = {o.id for o in db.query(models.Organismo.id).all()}

    # ---------------- Líneas de crédito (Creditos/lineacred) ----------------
    # El código de amortización de VFP (lineacred.tipo_calcu) NO coincide con la convención de la app.
    # Verificado contra la data real (motor reproduce las cuotas VFP al centavo, H-111):
    #   VFP 1 = Directo (interés flat: amort e interés constantes)  → app 3
    #   VFP 2 = Francés (cuota constante con IVA)                    → app 1
    #   VFP 3 = Francés (línea 9012, misma forma)                   → app 1
    # (app: 1=Francés, 2=Alemán, 3=Directo, 4=Francés c/gracia, 5=cuota fija). 4/5 no tienen créditos
    # migrados para confirmar → se copian verbatim.
    VFP_A_APP = {1: 3, 2: 1, 3: 1}
    p = os.path.join(bases, "Creditos", "lineacred.dbf")
    if os.path.exists(p) and not db.query(models.LineaCredito).first():
        rows = []
        with DbfReader(p) as r:
            for x in r.records():
                x = {k.lower(): v for k, v in x.items()}
                lid = I(x.get("no_linea"))
                if not lid:
                    continue
                tc_vfp = I(x.get("tipo_calcu"), 1) or 1
                tc = VFP_A_APP.get(tc_vfp, tc_vfp)
                rows.append({
                    "id": lid, "nombre": S(x.get("denominaci"))[:80] or f"Línea {lid}",
                    "cartera": I(x.get("cartera")), "tipo_calculo": tc,
                    "tna": D(x.get("tna")), "tasa_mora_diaria": D(x.get("nmoradia")),
                    "iva": Decimal("21"), "por_afecta": D(x.get("por_afecta"), "30"),
                    "porcent_pp": D(x.get("porcent_pp")), "seguro_pct": Decimal("0"),
                    "gastos_adm_pct": Decimal("0"),
                    "plazo_max": I(x.get("cuotas_cap"), 60) or 60,
                    "monto_max": D(x.get("capital_ma")),
                    "compania_seguros_id": None,
                    "activa": bool(x.get("lhabilitad")),
                })
        db.bulk_insert_mappings(models.LineaCredito, rows)
        db.commit()
        print(f"  líneas: {len(rows)}")

    # ---------------- Clientes (Creditos/maeclientes) ----------------
    p = os.path.join(bases, "Creditos", "maeclientes.dbf")
    if os.path.exists(p) and not db.query(models.Cliente).first():
        batch, total = [], 0
        vistos_id = set()
        with DbfReader(p) as r:
            for x in r.records():
                x = {k.lower(): v for k, v in x.items()}
                cuil = S(x.get("ccuil"))
                cid = S(x.get("cidcliente"))[:15]
                if not cid or cid in vistos_id:
                    continue
                vistos_id.add(cid)
                norg = I(x.get("norgano"))
                batch.append({
                    "id_cliente": cid[:15], "cuil": cuil[:11],
                    "dni": S(x.get("edni"))[:9], "apellido_nombre": S(x.get("capenom"))[:80],
                    "sexo": S(x.get("csexo"))[:1], "fecha_nacimiento": x.get("fnacim"),
                    "domicilio": S(x.get("cdomicilio"))[:120], "barrio": S(x.get("cbarrio"))[:40],
                    "localidad": S(x.get("clocalidad"))[:40], "telefono": S(x.get("ctelefono"))[:30],
                    "email": S(x.get("cemail"))[:80], "cbu": S(x.get("ccbucta"))[:23],
                    "debito_automatico": bool(x.get("ldebauto")), "sueldo": D(x.get("nsueldo")),
                    "categoria_funcion": S(x.get("ccatfun"))[:10], "fecha_ingreso": x.get("ffperm"),
                    "tipo_cliente": I(x.get("ntipocli")), "baja": bool(x.get("lbaja")),
                    "fecha_baja": x.get("fecbaja"), "motivo_baja": S(x.get("cmotbaja"))[:60],
                    "organismo_id": norg if norg in org_ids else None,
                })
                if len(batch) >= 2000:
                    db.bulk_insert_mappings(models.Cliente, batch)
                    db.commit(); total += len(batch); batch = []
        if batch:
            db.bulk_insert_mappings(models.Cliente, batch); db.commit(); total += len(batch)
        print(f"  clientes: {total}")

    db.close()
    print("ETL maestros OK")


if __name__ == "__main__":
    cargar(sys.argv[1])
