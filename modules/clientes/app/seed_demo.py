"""
Demo seed: crea 6 agencias (personas jurídicas) con agency_number y CBUs.
Ejecutar: docker compose exec clientes python -m app.seed_demo
"""
import sys
from app.db.session import SessionLocal
from app.models.client import Client, LegalClient, ClientCbu


AGENCIES = [
    {
        "code": "AG-001",
        "legal_name": "Lotería El Dorado S.A.",
        "tax_id": "30-71234567-8",
        "agency_number": "A001",
        "cbus": [
            {"cbu": "0720099620000001234501", "alias": "Cuenta principal"},
        ],
    },
    {
        "code": "AG-002",
        "legal_name": "Quiniela San Martín S.R.L.",
        "tax_id": "30-68456789-2",
        "agency_number": "A002",
        "cbus": [
            {"cbu": "0720099620000002345602", "alias": "BNA operaciones"},
        ],
    },
    {
        "code": "AG-003",
        "legal_name": "Bingo del Centro S.A.",
        "tax_id": "30-59876543-1",
        "agency_number": "A003",
        "cbus": [
            {"cbu": "0110012820000034567803", "alias": "Cuenta Galicia"},
            {"cbu": "0140018920000045678904", "alias": "Cuenta BBVA"},
        ],
    },
    {
        "code": "AG-004",
        "legal_name": "Lotería del Sur S.R.L.",
        "tax_id": "30-64321098-7",
        "agency_number": "A004",
        "cbus": [
            {"cbu": "0720099620000056789005", "alias": "Macro cta cte"},
        ],
    },
    {
        "code": "AG-005",
        "legal_name": "Casino Royal S.A.",
        "tax_id": "30-77654321-9",
        "agency_number": "A005",
        "cbus": [
            {"cbu": "0170099620000067890106", "alias": "ICBC principal"},
        ],
    },
    {
        "code": "AG-006",
        "legal_name": "Quiniela Los Andes S.R.L.",
        "tax_id": "30-55123456-4",
        "agency_number": "A006",
        "cbus": [
            {"cbu": "0720099620000078901207", "alias": "Santander Río"},
        ],
    },
]


def run():
    db = SessionLocal()
    try:
        for ag in AGENCIES:
            existing = db.query(Client).filter(Client.code == ag["code"]).first()
            if existing:
                print(f"[seed_demo] {ag['code']} ya existe, saltando.")
                continue

            client = Client(
                client_type="LEGAL",
                code=ag["code"],
                is_active=True,
                country="AR",
                created_by_user_id=1,
            )
            db.add(client)
            db.flush()

            legal = LegalClient(
                client_id=client.id,
                legal_name=ag["legal_name"],
                tax_id=ag["tax_id"],
                tax_id_type="CUIT",
                agency_number=ag["agency_number"],
            )
            db.add(legal)
            db.flush()

            for cbu_data in ag["cbus"]:
                cbu = ClientCbu(
                    client_id=client.id,
                    cbu=cbu_data["cbu"],
                    alias=cbu_data["alias"],
                    is_active=True,
                    created_by=1,
                )
                db.add(cbu)

            print(f"[seed_demo] Creada agencia {ag['agency_number']} - {ag['legal_name']}")

        db.commit()
        print("[seed_demo] Agencias de demo cargadas correctamente.")
    except Exception as e:
        db.rollback()
        print(f"[seed_demo] Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    run()
