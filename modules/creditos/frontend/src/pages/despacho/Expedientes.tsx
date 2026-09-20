import { useEffect, useState } from "react";
import { api } from "../../api";
import DataTable, { Col } from "../../components/DataTable";

const LIMIT = 25;

// Expedientes = trámites tipo E* (Seguro de vida, Sepelio, Subsidio, etc.).
// Dato real de Mesa de Entradas (tramites/pases). Antes esta pantalla usaba un
// flujo in-app vacío; ahora muestra los expedientes reales con su recorrido.
export default function Expedientes() {
  const [rows, setRows] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [busq, setBusq] = useState("");
  const [q, setQ] = useState("");
  const [pases, setPases] = useState<any>(null);

  async function cargar(off = 0, query = q) {
    const d = await api.tramites({ solo_expedientes: true, q: query || undefined, limit: LIMIT, offset: off });
    setRows(d.items); setTotal(d.total); setOffset(off);
  }
  useEffect(() => { cargar(0, q); }, [q]);
  async function verPases(id: number) { setPases(await api.tramitePases(id)); }

  const cols: Col[] = [
    { key: "fecha_alta", label: "Fecha", render: (t) => t.fecha_alta || "-" },
    { key: "expediente", label: "Expediente" },
    { key: "referencia", label: "Referencia" },
    { key: "iniciador", label: "Iniciador / Asegurado" },
    { key: "oficina", label: "Oficina" },
    { key: "estado", label: "Estado" },
    { key: "acc", label: "", align: "right", render: (t) => (
      <a href="#" onClick={(e) => { e.preventDefault(); verPases(t.id); }}>ver pases</a>
    ) },
  ];

  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2 style={{ margin: 0 }}>Expedientes y pases</h2>
        <form onSubmit={(e) => { e.preventDefault(); setQ(busq); }}>
          <input value={busq} onChange={(e) => setBusq(e.target.value)} placeholder="Buscar iniciador / referencia" style={{ marginBottom: 0, width: 240 }} />
        </form>
      </div>
      <p className="muted" style={{ marginTop: "0.5rem" }}>Expedientes de Mesa de Entradas (Seguro de vida, Sepelio, Subsidios…). <b>{Number(total).toLocaleString("es-AR")}</b> expedientes.</p>
      <DataTable columns={cols} rows={rows} total={total} limit={LIMIT} offset={offset}
                 onPage={(off) => cargar(off)} rowKey={(t) => t.id} emptyText="Sin expedientes" />

      {pases && (
        <div style={{ borderTop: "1px solid var(--borde)", marginTop: "1rem", paddingTop: "0.8rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h3 style={{ margin: 0 }}>Pases de {pases.expediente} <span className="muted">— {pases.cantidad} pase(s)</span></h3>
            <button onClick={() => setPases(null)} style={{ background: "var(--ink-faint)" }}>Cerrar</button>
          </div>
          <p className="muted">{pases.referencia}</p>
          <table>
            <thead><tr><th>#</th><th>Fecha</th><th>Origen</th><th>Destino</th><th>Proveído / texto</th><th>Activo</th></tr></thead>
            <tbody>
              {pases.pases.map((p: any) => (
                <tr key={p.orden}>
                  <td>{p.orden}</td><td>{p.fecha || "-"}</td>
                  <td>{p.oficina_origen}</td><td>{p.oficina_destino}</td>
                  <td>{p.texto || "-"}</td><td>{p.activo ? "Sí" : "—"}</td>
                </tr>
              ))}
              {!pases.pases.length && <tr><td colSpan={6} className="muted">El expediente no tiene pases registrados.</td></tr>}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
