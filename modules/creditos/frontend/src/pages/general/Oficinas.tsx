import { useEffect, useState } from "react";
import { api } from "../../api";
import DataTable, { Col } from "../../components/DataTable";
import LimpiarFiltros from "../../components/LimpiarFiltros";

const COLS: Col[] = [
  { key: "id", label: "N°", sortable: true },
  { key: "denominacion", label: "Denominación", sortable: true },
  { key: "telefono_interno", label: "Interno", sortable: true, render: (o) => o.telefono_interno || "-" },
  { key: "telefono_linea", label: "Línea", sortable: true, render: (o) => o.telefono_linea || "-" },
  { key: "interna", label: "Interna", sortable: true, render: (o) => (o.interna ? "Sí" : "—") },
];

export default function Oficinas() {
  const [rows, setRows] = useState<any[]>([]);
  const [q, setQ] = useState("");
  useEffect(() => { api.oficinas().then(setRows); }, []);

  const filtradas = rows.filter((o) =>
    !q || o.denominacion.toLowerCase().includes(q.toLowerCase()) || String(o.id).includes(q));

  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "0.5rem" }}>
        <h2 style={{ margin: 0 }}>Oficinas / Dependencias</h2>
        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar oficina" style={{ marginBottom: 0, width: 220 }} />
          <LimpiarFiltros activo={!!q} onClear={() => setQ("")} />
        </div>
      </div>
      <p className="muted" style={{ marginTop: "0.5rem" }}>Maestro de oficinas internas. Fuente: oficinas. {rows.length} dependencias.</p>
      <DataTable columns={COLS} rows={filtradas} rowKey={(o) => o.id}
                 clientSort pageSize={25} defaultSort="id" emptyText="Sin oficinas" />
    </div>
  );
}
