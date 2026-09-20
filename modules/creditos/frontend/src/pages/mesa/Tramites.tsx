import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../../api";
import DataTable, { Col } from "../../components/DataTable";
import VolverFicha from "../../components/VolverFicha";

const LIMIT = 25;

export default function Tramites() {
  const [tipos, setTipos] = useState<any[]>([]);
  const [tipo, setTipo] = useState("");
  const [estado, setEstado] = useState("");
  const [sp] = useSearchParams();
  const [busq, setBusq] = useState(sp.get("q") || "");
  const [q, setQ] = useState(sp.get("q") || "");
  const [rows, setRows] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [pases, setPases] = useState<any>(null);

  useEffect(() => { api.tramiteTipos().then(setTipos); }, []);

  async function verPases(id: number) { setPases(await api.tramitePases(id)); }

  async function cargar(off = 0) {
    const d = await api.tramites({
      tipo: tipo || undefined, estado: estado || undefined,
      q: q || undefined, limit: LIMIT, offset: off,
    });
    setRows(d.items); setTotal(d.total); setOffset(off);
  }
  useEffect(() => { cargar(0); }, [tipo, estado, q]);

  const cols: Col[] = [
    { key: "fecha_alta", label: "Fecha", render: (t) => t.fecha_alta || "-" },
    { key: "expediente", label: "Trámite" },
    { key: "referencia", label: "Referencia" },
    { key: "iniciador", label: "Iniciador / Asegurado" },
    { key: "oficina", label: "Oficina" },
    { key: "hojas", label: "Hojas" },
    { key: "estado", label: "Estado" },
    { key: "acc", label: "", align: "right", render: (t) => (
      <a href="#" onClick={(e) => { e.preventDefault(); verPases(t.id); }}>ver pases</a>
    ) },
  ];

  return (
    <>
      <VolverFicha />
      <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
        <h2 style={{ margin: 0 }}>Consulta de trámites</h2>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <form onSubmit={(e) => { e.preventDefault(); setQ(busq); }}>
            <input value={busq} onChange={(e) => setBusq(e.target.value)} placeholder="Buscar iniciador / referencia" style={{ marginBottom: 0 }} />
          </form>
          <select value={tipo} onChange={(e) => setTipo(e.target.value)} style={{ width: "auto", marginBottom: 0, maxWidth: 200 }}>
            <option value="">Todos los tipos</option>
            {tipos.map((t) => <option key={t.codigo} value={t.codigo}>{t.codigo} · {t.corta || t.descripcion}</option>)}
          </select>
          <select value={estado} onChange={(e) => setEstado(e.target.value)} style={{ width: "auto", marginBottom: 0 }}>
            <option value="">Todo estado</option><option value="A">En trámite</option>
            <option value="C">Cerrado</option><option value="B">Baja</option>
          </select>
        </div>
      </div>
      <p className="muted" style={{ marginTop: "0.5rem" }}>Notas y expedientes de Mesa de Entradas. <b>{Number(total).toLocaleString("es-AR")}</b> trámites.</p>
      <DataTable columns={cols} rows={rows} total={total} limit={LIMIT} offset={offset}
                 onPage={(off) => cargar(off)} rowKey={(t) => t.id} emptyText="Sin trámites" />

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
                  <td>Of. {p.oficina_origen}</td><td>Of. {p.oficina_destino}</td>
                  <td>{p.texto || "-"}</td><td>{p.activo ? "Sí" : "—"}</td>
                </tr>
              ))}
              {!pases.pases.length && <tr><td colSpan={6} className="muted">El trámite no tiene pases registrados.</td></tr>}
            </tbody>
          </table>
        </div>
      )}
    </div>
    </>
  );
}
