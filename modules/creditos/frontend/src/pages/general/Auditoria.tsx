import { useEffect, useState } from "react";
import { api } from "../../api";
import DataTable, { Col } from "../../components/DataTable";

const LIMIT = 25;
const num = (v: number) => Number(v).toLocaleString("es-AR");
const dt = (v: string | null) => (v ? new Date(v).toLocaleString("es-AR") : "—");

type Tab = "detalle" | "usuario" | "maquina";

export default function Auditoria() {
  const [tab, setTab] = useState<Tab>("detalle");

  // Detalle (log paginado)
  const [eventos, setEventos] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [usr, setUsr] = useState("");
  const [filtro, setFiltro] = useState("");

  // Resúmenes (por usuario / por máquina)
  const [resumen, setResumen] = useState<any>(null);

  async function cargar(off: number, usuario: string) {
    const d = await api.auditoria({ usuario, limit: LIMIT, offset: off });
    setEventos(d.items); setTotal(d.total); setOffset(off);
  }
  useEffect(() => { if (tab === "detalle") cargar(0, filtro); }, [filtro, tab]);
  useEffect(() => {
    if (tab === "usuario" || tab === "maquina") api.auditoriaResumen(tab).then(setResumen);
  }, [tab]);

  const cols: Col[] = [
    { key: "fecha_hora", label: "Fecha/hora", render: (e) => dt(e.fecha_hora) },
    { key: "usuario", label: "Usuario" },
    { key: "maquina", label: "Máquina", render: (e) => e.maquina || "—" },
    { key: "proceso", label: "Proceso" },
    { key: "opcion", label: "Opción" },
  ];

  const tabBtn = (t: Tab, label: string) => (
    <button onClick={() => setTab(t)}
            style={{ background: tab === t ? undefined : "transparent",
                     color: tab === t ? undefined : "var(--fg, inherit)",
                     border: "1px solid var(--border, #ccc)" }}>{label}</button>
  );

  return (
    <div className="card">
      <h2 style={{ marginTop: 0 }}>Auditoría</h2>
      <div style={{ display: "flex", gap: "0.4rem", marginBottom: "0.8rem" }}>
        {tabBtn("detalle", "Detalle")}
        {tabBtn("usuario", "Por usuario")}
        {tabBtn("maquina", "Por máquina")}
      </div>

      {tab === "detalle" && (
        <>
          <form onSubmit={(e) => { e.preventDefault(); setFiltro(usr); }}
                style={{ display: "flex", gap: "0.5rem", alignItems: "end", marginBottom: "0.8rem" }}>
            <div style={{ flex: 1 }}><label>Filtrar por usuario</label>
              <input value={usr} onChange={(e) => setUsr(e.target.value)} style={{ marginBottom: 0 }} placeholder="(vacío = todos)" /></div>
            <button type="submit">Consultar</button>
          </form>
          <DataTable columns={cols} rows={eventos} total={total} limit={LIMIT} offset={offset}
                     onPage={(off) => cargar(off, filtro)} emptyText="Sin eventos" />
        </>
      )}

      {(tab === "usuario" || tab === "maquina") && resumen && (
        <>
          <p className="muted">{num(resumen.total_eventos)} eventos · {num(resumen.cantidad)} {tab === "usuario" ? "usuarios" : "máquinas"} (muestra: últimos ~50 mil eventos del log en producción).</p>
          <table>
            <thead><tr><th>{tab === "usuario" ? "Usuario" : "Máquina"}</th><th style={{ textAlign: "right" }}>Eventos</th><th style={{ textAlign: "right" }}>Procesos distintos</th><th>Primero</th><th>Último</th></tr></thead>
            <tbody>
              {resumen.items.map((r: any) => (
                <tr key={r.clave}>
                  <td>{r.clave}</td>
                  <td style={{ textAlign: "right" }}>{num(r.eventos)}</td>
                  <td style={{ textAlign: "right" }}>{num(r.procesos_distintos)}</td>
                  <td>{dt(r.primero)}</td><td>{dt(r.ultimo)}</td>
                </tr>
              ))}
              {!resumen.items.length && <tr><td colSpan={5} className="muted">Sin eventos</td></tr>}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}
