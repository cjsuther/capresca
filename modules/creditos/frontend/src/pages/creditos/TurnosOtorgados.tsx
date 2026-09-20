import { useEffect, useState } from "react";
import { api } from "../../api";
import DataTable, { Col } from "../../components/DataTable";

const money = (v: string | number) =>
  Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });
const LIMIT = 25;

export default function TurnosOtorgados() {
  const [rows, setRows] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [busq, setBusq] = useState("");
  const [q, setQ] = useState("");
  const [tipo, setTipo] = useState("");
  const [usado, setUsado] = useState("");

  async function cargar(off = 0) {
    const d = await api.turnosOtorgados({
      q: q || undefined, tipo: tipo || undefined,
      usado: usado === "" ? undefined : usado === "si",
      limit: LIMIT, offset: off,
    });
    setRows(d.items); setTotal(d.total); setOffset(off);
  }
  useEffect(() => { cargar(0); }, [q, tipo, usado]);

  const cols: Col[] = [
    { key: "fecha", label: "Fecha", render: (t) => t.fecha || "-" },
    { key: "periodo", label: "Período" },
    { key: "tipo", label: "Tipo" },
    { key: "numero", label: "N° turno" },
    { key: "apellido_nombre", label: "Solicitante" },
    { key: "cuil", label: "CUIL" },
    { key: "sueldo", label: "Sueldo", align: "right", render: (t) => money(t.sueldo) },
    { key: "usado", label: "Usado", render: (t) => (t.usado ? "Sí" : "—") },
    { key: "autorizado", label: "Autorizado", render: (t) => (t.autorizado ? "Sí" : "—") },
  ];

  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
        <h2 style={{ margin: 0 }}>Turnos otorgados</h2>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <form onSubmit={(e) => { e.preventDefault(); setQ(busq); }}>
            <input value={busq} onChange={(e) => setBusq(e.target.value)} placeholder="Buscar solicitante / CUIL" style={{ marginBottom: 0 }} />
          </form>
          <select value={tipo} onChange={(e) => setTipo(e.target.value)} style={{ width: "auto", marginBottom: 0 }}>
            <option value="">Todo tipo</option><option value="TODO">TODO</option><option value="AGAP">AGAP</option>
          </select>
          <select value={usado} onChange={(e) => setUsado(e.target.value)} style={{ width: "auto", marginBottom: 0 }}>
            <option value="">Usado/no</option><option value="si">Usados</option><option value="no">No usados</option>
          </select>
          <button onClick={() => api.descargarTurnosExcel({
            tipo: tipo || undefined, q: q || undefined,
            usado: usado === "" ? undefined : usado === "si",
          })} style={{ background: "var(--ok)" }}>Excel</button>
        </div>
      </div>
      <p className="muted" style={{ marginTop: "0.5rem" }}>Turnos para presentar la solicitud de crédito. <b>{Number(total).toLocaleString("es-AR")}</b> turnos.</p>
      <DataTable columns={cols} rows={rows} total={total} limit={LIMIT} offset={offset}
                 onPage={(off) => cargar(off)} rowKey={(t, i) => `${t.periodo}-${t.tipo}-${t.numero}-${i}`}
                 emptyText="Sin turnos" />
    </div>
  );
}
