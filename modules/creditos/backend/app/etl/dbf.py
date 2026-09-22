"""Lector de tablas Visual FoxPro (.DBF) para el ETL — sin dependencias externas.

Soporta los tipos usados por CCyPP: C (char), N (numérico), F (float),
I (entero 4 bytes), D (fecha), T (datetime), L (lógico), Y (currency),
B (double), M (memo -> se devuelve el puntero de bloque).

Uso en streaming para tablas grandes (tmpdev.DBF ~ 2,6M registros):

    from app.etl.dbf import DbfReader
    with DbfReader("tmpdev.DBF") as r:
        print(r.record_count, [f.name for f in r.fields])
        for row in r.records():        # generador, no carga todo en memoria
            ...
"""
from __future__ import annotations

import os
import struct
import datetime
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterator


@dataclass
class Field:
    name: str
    type: str
    length: int
    decimals: int


class DbfReader:
    def __init__(self, path: str):
        self.path = path
        self._f = open(path, "rb")
        hdr = self._f.read(32)
        self.version = hdr[0]
        self.record_count = struct.unpack("<I", hdr[4:8])[0]
        self.header_len = struct.unpack("<H", hdr[8:10])[0]
        self.record_len = struct.unpack("<H", hdr[10:12])[0]
        self.fields: list[Field] = []
        self._f.seek(32)
        while True:
            fd = self._f.read(32)
            if not fd or fd[0] == 0x0D:
                break
            name = fd[0:11].split(b"\x00")[0].decode("latin-1")
            self.fields.append(Field(name, chr(fd[11]), fd[16], fd[17]))
        # Memo file (.fpt/.FPT/.dbt) para dereferenciar campos M. Se resuelve por el NOMBRE BASE (sin la
        # extensión .dbf), no recortando un carácter (el bug previo buscaba "archivo.dbfpt" y nunca lo hallaba
        # → todos los memos salían vacíos). H-165.
        self._fpt = None
        self._fpt_block = 64
        stem = os.path.splitext(path)[0]
        for ext in (".fpt", ".FPT", ".Fpt", ".dbt", ".DBT"):
            cand = stem + ext
            if os.path.exists(cand):
                self._fpt = open(cand, "rb")
                head = self._fpt.read(512)
                self._fpt_block = struct.unpack(">H", head[6:8])[0] or 64
                break

    def _memo(self, raw: bytes) -> str:
        if not self._fpt or len(raw) != 4:
            return ""
        block = struct.unpack("<I", raw)[0]
        if not block:
            return ""
        off = block * self._fpt_block
        self._fpt.seek(off)
        head = self._fpt.read(8)
        if len(head) < 8:
            return ""
        length = struct.unpack(">I", head[4:8])[0]
        return self._fpt.read(length).decode("latin-1", "ignore").replace("\x00", "").strip()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self._f.close()

    # ---- decodificación de tipos VFP ----
    @staticmethod
    def _date(s: str):
        s = s.strip()
        if len(s) == 8 and s.isdigit():
            try:  # datos con fechas corruptas (año 0, mes 0) → None
                return datetime.date(int(s[:4]), int(s[4:6]), int(s[6:8]))
            except ValueError:
                return None
        return None

    @staticmethod
    def _datetime(b: bytes):
        jd, ms = struct.unpack("<ii", b)
        if jd == 0:
            return None
        try:
            d = datetime.date.fromordinal(jd - 1721425)
            return datetime.datetime.combine(d, datetime.time()) + datetime.timedelta(milliseconds=ms)
        except (ValueError, OverflowError):
            return None

    def _decode(self, field: Field, raw: bytes):
        t = field.type
        if t == "C":
            # Algunos campos traen bytes NUL (0x00) de basura; PostgreSQL los
            # rechaza en text. Se eliminan (ver H-025).
            return raw.decode("latin-1").replace("\x00", "").rstrip()
        if t in ("N", "F"):
            s = raw.decode("latin-1").strip()
            if s in ("", ".") or "*" in s:  # '*' = overflow numérico en VFP
                return None
            try:
                return Decimal(s) if (field.decimals or "." in s) else int(s)
            except Exception:
                return None
        if t == "I":
            return struct.unpack("<i", raw)[0]
        if t == "Y":  # currency: int64 escalado por 10000
            return Decimal(struct.unpack("<q", raw)[0]) / Decimal(10000)
        if t == "B":  # double
            return struct.unpack("<d", raw)[0]
        if t == "D":
            return self._date(raw.decode("latin-1"))
        if t == "T":
            return self._datetime(raw)
        if t == "L":
            c = raw.decode("latin-1").upper()
            return True if c == "T" else False if c == "F" else None
        if t == "M":
            return self._memo(raw)
        return raw  # otros

    def records(self, include_deleted: bool = False) -> Iterator[dict]:
        self._f.seek(self.header_len)
        for _ in range(self.record_count):
            rec = self._f.read(self.record_len)
            if len(rec) < self.record_len:
                break
            deleted = rec[0] == 0x2A
            if deleted and not include_deleted:
                continue
            o = 1
            row = {"_deleted": deleted}
            for fld in self.fields:
                row[fld.name] = self._decode(fld, rec[o:o + fld.length])
                o += fld.length
            yield row
