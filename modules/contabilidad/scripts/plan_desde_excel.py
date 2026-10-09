"""Convierte el plan de cuentas que exporta el sistema anterior (Excel) en `app/plan_cuentas.csv`,
que es lo que siembra el módulo.

    python scripts/plan_desde_excel.py "../../externalfiles/Plan de cuentas excel.xlsx"

El Excel trae sólo código, nombre e imputable; el resto se deduce:
  - Jerarquía por máscara (1.1.1.2.001 → su madre es 1.1.1.2.000), igual que la mostraba el sistema
    anterior. Las madres que faltan en el archivo se crean como cuentas de agrupación.
  - Rubro por grupo: 1 activo, 2 pasivo, 3 patrimonio, 4.1 ingresos, 4.2/4.3 egresos,
    5 (cuentas de movimiento) y 6 orden, 7 (REI) egreso.
  - Una cuenta sin subcuentas es imputable aunque el Excel no la marque. Una con subcuentas conserva
    la marca del Excel: el plan anterior numeraba de corrido (1.2.3.9 sigue en 1.2.4.0) y cuentas
    como 1.2.4.0.000 Patentes reciben asientos aunque por máscara tengan "hijas".
  - Saldo normal por rubro (las amortizaciones acumuladas y previsiones del activo son acreedoras) y
    ajuste por inflación para el patrimonio y los bienes de uso.

Imprime lo que tuvo que corregir para que lo revise el contador.
"""
import csv
import re
import sys
from pathlib import Path

import openpyxl

DESTINO = Path(__file__).resolve().parent.parent / "app" / "plan_cuentas.csv"
CODIGO = re.compile(r"^\s*(\d(?:\.\d+){4})\s+(.*\S)\s*$")
TILDE = "✓"
BIENES_DE_USO = ("1.2.3.", "1.2.4.", "1.2.5.", "1.2.6.")


def nivel(codigo: str) -> int:
    """0 = raíz (1.0.0.0.000); el índice del último segmento que no es cero."""
    return max(i for i, s in enumerate(codigo.split(".")) if s.strip("0"))


def madre(codigo: str) -> str:
    segs = codigo.split(".")
    i = nivel(codigo)
    if i == 0:
        return ""
    segs[i] = "0" * len(segs[i])
    return ".".join(segs)


def rubro(codigo: str) -> str:
    raiz, segundo = codigo.split(".")[:2]
    if raiz == "4":
        return "EGRESO" if segundo in ("2", "3") else "INGRESO"
    return {"1": "ACTIVO", "2": "PASIVO", "3": "PATRIMONIO", "5": "ORDEN", "6": "ORDEN",
            "7": "EGRESO"}[raiz]


def saldo_normal(codigo: str, nombre: str, r: str) -> str:
    if r == "ACTIVO":
        return "ACREEDOR" if re.search(r"(?i)amort|previs", nombre) else "DEUDOR"
    return "ACREEDOR" if r in ("PASIVO", "PATRIMONIO", "INGRESO") else "DEUDOR"


def leer(ruta: str) -> list[tuple[str, str, bool]]:
    hoja = openpyxl.load_workbook(ruta, data_only=True).active
    filas = []
    for celdas in hoja.iter_rows(min_row=4, values_only=True):
        # Algunas filas vienen corridas una columna a la derecha: el texto está en B y la marca en D.
        texto, marca = (celdas[0], celdas[2]) if celdas[0] else (celdas[1], celdas[3])
        if not texto or "Página" in str(celdas):      # el pie de cada página del listado
            continue
        m = CODIGO.match(str(texto))
        if not m:
            sys.exit(f"Fila que no se entiende: {celdas}")
        filas.append((m.group(1), re.sub(r"\s+", " ", m.group(2)), marca == TILDE))
    return filas


def convertir(filas):
    cuentas = {c: [n, imp] for c, n, imp in filas}
    creadas = []
    for c, *_ in filas:
        m = madre(c)
        while m and m not in cuentas:
            cuentas[m] = ["(sin nombre)", False]
            creadas.append(m)
            m = madre(m)
    con_hijas = {madre(c) for c in cuentas}
    pasadas_a_imputable = []
    for c, datos in cuentas.items():
        if c not in con_hijas and not datos[1]:
            datos[1] = True
            pasadas_a_imputable.append(c)
    salida = []
    for c in sorted(cuentas, key=lambda x: [int(s) for s in x.split(".")]):
        nombre, imputable = cuentas[c]
        r = rubro(c)
        salida.append({"codigo": c, "nombre": nombre, "rubro": r, "imputable": imputable,
                       "saldo_normal": saldo_normal(c, nombre, r),
                       "ajustable": r == "PATRIMONIO" or c.startswith(BIENES_DE_USO)})
    imputables_con_hijas = [c for c in con_hijas if c and cuentas[c][1]]
    return salida, sorted(creadas), sorted(pasadas_a_imputable), sorted(imputables_con_hijas)


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    filas = leer(sys.argv[1])
    salida, creadas, pasadas, imp_hijas = convertir(filas)
    with DESTINO.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(salida[0]))
        w.writeheader()
        for fila in salida:
            w.writerow({**fila, "imputable": int(fila["imputable"]), "ajustable": int(fila["ajustable"])})
    print(f"{len(filas)} cuentas en el Excel → {len(salida)} en {DESTINO.name}")
    print(f"\nMadres que faltaban, creadas como agrupación ({len(creadas)}): {', '.join(creadas)}")
    print(f"\nSin subcuentas y sin marca, pasan a imputables ({len(pasadas)}): {', '.join(pasadas)}")
    print(f"\nImputables con subcuentas, se respeta el Excel ({len(imp_hijas)}): {', '.join(imp_hijas)}")


if __name__ == "__main__":
    main()
