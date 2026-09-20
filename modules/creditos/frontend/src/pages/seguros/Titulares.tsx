import { useEffect, useState } from "react";
import { api } from "../../api";
import DataTable, { Col } from "../../components/DataTable";

const LIMIT = 25;

export default function Titulares() {
  const [rows, setRows] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [busq, setBusq] = useState("");
  const [q, setQ] = useState("");

  async function cargar(off = 0, query = q) {
    const d = await api.titularesSeguro({ q: query || undefined, limit: LIMIT, offset: off });
    setRows(d.items); setTotal(d.total); setOffset(off);
  }
  useEffect(() => { cargar(0, q); }, [q]);

  const cols: Col[] = [
    { key: "apellido_nombre", label: "Apellido y nombre" },
    { key: "cuil", label: "CUIL" },
    { key: "tipo_titular", label: "Tipo" },
    { key: "sexo", label: "Sexo" },
    { key: "no_agente", label: "N° agente" },
    { key: "fecha_nac", label: "Nacimiento", render: (t) => t.fecha_nac || "-" },
    { key: "localidad", label: "Localidad" },
  ];

  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2 style={{ margin: 0 }}>Titulares de seguro</h2>
        <form onSubmit={(e) => { e.preventDefault(); setQ(busq); }}>
          <input value={busq} onChange={(e) => setBusq(e.target.value)} placeholder="Buscar apellido / CUIL" style={{ marginBottom: 0, width: 240 }} />
        </form>
      </div>
      <p className="muted" style={{ marginTop: "0.5rem" }}>Maestro de titulares del seguro de vida colectivo. Fuente: titulares. <b>{Number(total).toLocaleString("es-AR")}</b> titulares.</p>
      <DataTable columns={cols} rows={rows} total={total} limit={LIMIT} offset={offset}
                 onPage={(off) => cargar(off)} rowKey={(t) => t.id} emptyText="Sin titulares" />
    </div>
  );
}
