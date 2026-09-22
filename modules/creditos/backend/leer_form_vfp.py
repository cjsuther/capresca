"""Lee un formulario VFP (.scx + .sct) y vuelca objetos, propiedades y código.

Uso: python leer_form_vfp.py <ruta.scx> [--code]
Un .scx es un DBF; su memo (propiedades/métodos) está en el .sct hermano.
"""
import os
import struct
import sys

from app.etl.dbf import DbfReader


def abrir(scx: str) -> list[dict]:
    r = DbfReader(scx)
    sct = scx[:-1] + "t"  # .scx -> .sct  (y .SCX -> .SCt, probamos ambos)
    for cand in (sct, scx[:-3] + "sct", scx[:-3] + "SCT"):
        if os.path.exists(cand):
            r._fpt = open(cand, "rb")
            head = r._fpt.read(512)
            r._fpt_block = struct.unpack(">H", head[6:8])[0] or 64
            break
    return list(r.records())


def prop(props: str, nombre: str) -> str:
    for line in (props or "").replace("\r\n", "\n").split("\n"):
        if line.strip().lower().startswith(nombre.lower() + " ="):
            return line.split("=", 1)[1].strip().strip('"')
    return ""


def main():
    scx = sys.argv[1]
    show_code = "--code" in sys.argv
    recs = abrir(scx)
    print(f"# {os.path.basename(scx)} — {len(recs)} objetos\n")
    for x in recs:
        obj = (x.get("OBJNAME") or "").strip()
        base = (x.get("BASECLASS") or "").strip()
        cls = (x.get("CLASS") or "").strip()
        if not obj:
            continue
        props = x.get("PROPERTIES") or ""
        cap = prop(props, "Caption")
        rowsrc = prop(props, "RecordSource") or prop(props, "RowSource")
        ctrl = prop(props, "ControlSource")
        extra = " | ".join(filter(None, [
            f'cap="{cap}"' if cap else "",
            f"rowsrc={rowsrc}" if rowsrc else "",
            f"ctrlsrc={ctrl}" if ctrl else "",
        ]))
        print(f"[{base or cls}] {obj}  {extra}")
        if show_code:
            meth = (x.get("METHODS") or "").strip()
            if meth:
                print("    " + meth.replace("\r\n", "\n").replace("\n", "\n    "))
                print()


if __name__ == "__main__":
    main()
