import { useEffect, useState } from "react";
import { api } from "../../api";
import DataTable, { Col } from "../../components/DataTable";

const money = (v: string | number) =>
  Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });
const LIMIT = 25;

export default function SinDebito() {
  const [rows, setRows] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [saldo, setSaldo] = useState(0);
  const [offset, setOffset] = useState(0);
  const [busq, setBusq] = useState("");
  const [q, setQ] = useState("");
  const [lineas, setLineas] = useState<any[]>([]);
  const [lineaId, setLineaId] = useState("");

  useEffect(() => { api.lineas().then(setLineas); }, []);

  async function cargar(off = 0, query = q) {
    const d = await api.creditosSinDebito({
      q: query || undefined, linea_id: lineaId ? Number(lineaId) : undefined,
      limit: LIMIT, offset: off,
    });
    setRows(d.items); setTotal(d.total); setSaldo(d.total_saldo); setOffset(off);
  }
  useEffect(() => { cargar(0, q); }, [q, lineaId]);

  const cols: Col[] = [
    { key: "credito_id", label: "Crédito" },
    { key: "cliente", label: "Cliente" },
    { key: "cuil", label: "CUIL" },
    { key: "linea", label: "Línea" },
    { key: "sueldo", label: "Sueldo", align: "right", render: (r) => money(r.sueldo) },
    { key: "saldo", label: "Saldo", align: "right", render: (r) => money(r.saldo) },
  ];

  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
        <h2 style={{ margin: 0 }}>Créditos sin débito automático</h2>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <form onSubmit={(e) => { e.preventDefault(); setQ(busq); }}>
            <input value={busq} onChange={(e) => setBusq(e.target.value)} placeholder="Buscar cliente / CUIL" style={{ marginBottom: 0 }} />
          </form>
          <select value={lineaId} onChange={(e) => setLineaId(e.target.value)} style={{ width: "auto", marginBottom: 0, maxWidth: 220 }}>
            <option value="">Todas las líneas</option>
            {lineas.map((l) => <option key={l.id} value={l.id}>{l.nombre}</option>)}
          </select>
        </div>
      </div>
      <p className="muted" style={{ marginTop: "0.5rem" }}>
        Créditos activos cuyo cliente no tiene CBU cargado: requieren cobro manual (no entran al padrón de débito).
        {" "}<b>{Number(total).toLocaleString("es-AR")}</b> créditos · saldo {money(saldo || 0)}.
      </p>
      <DataTable columns={cols} rows={rows} total={total} limit={LIMIT} offset={offset}
                 onPage={(off) => cargar(off)} rowKey={(r) => r.credito_id} emptyText="Sin resultados" />
    </div>
  );
}
