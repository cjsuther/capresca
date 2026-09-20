import { useState } from "react";
import { api } from "../../api";
import DataTable, { Col } from "../../components/DataTable";
import LimpiarFiltros from "../../components/LimpiarFiltros";

const money = (v: string | number) =>
  Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });

const COLS: Col[] = [
  { key: "cod_agencia", label: "Agencia", sortable: true, render: (it) => it.cod_agencia || it.no_agencia },
  { key: "subagencia", label: "Sub", sortable: true },
  { key: "juego", label: "Juego", sortable: true },
  { key: "no_sorteo", label: "N° Sorteo", sortable: true, align: "right" },
  { key: "fecha_vto", label: "Vto.", sortable: true, render: (it) => it.fecha_vto || "-" },
  { key: "dias_atraso", label: "Días atr.", sortable: true, align: "right",
    render: (it) => <span style={{ color: it.dias_atraso > 0 ? "var(--crit)" : undefined }}>{it.dias_atraso}</span> },
  { key: "moneda", label: "Moneda", align: "left" },
  { key: "total", label: "Total", sortable: true, align: "right", sortValue: (it) => Number(it.total), render: (it) => money(it.total) },
  { key: "total_gral", label: "Total Gral.", sortable: true, align: "right", sortValue: (it) => Number(it.total_gral), render: (it) => <b>{money(it.total_gral)}</b> },
];

// Informe de deuda de agencia (22555 / frm225550000infdeuage): liquidaciones impagas
// de una agencia (o todas) por rango de vencimiento, con días de atraso.
export default function DeudaAgencia() {
  const [cod, setCod] = useState("");
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");

  async function buscar(e?: React.FormEvent) {
    e?.preventDefault(); setError("");
    try {
      setData(await api.deudaAgenciaInforme({ cod, desde, hasta }));
    } catch (err: any) { setError(err.message); setData(null); }
  }

  return (
    <>
      <div className="card">
        <h2 style={{ marginTop: 0 }}>Informe de deuda de agencia</h2>
        <p className="muted">Liquidaciones impagas por agencia y rango de vencimiento. Fuente: <code>frm225550000infdeuage</code> (menú 22555).</p>
        <form onSubmit={buscar} style={{ display: "flex", gap: "0.5rem", alignItems: "end", flexWrap: "wrap" }}>
          <div><label>Código de agencia (opcional)</label><input value={cod} onChange={(e) => setCod(e.target.value)} placeholder="todas" style={{ marginBottom: 0, width: 140 }} /></div>
          <div><label>Vto. desde</label><input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} style={{ marginBottom: 0 }} /></div>
          <div><label>Vto. hasta</label><input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} style={{ marginBottom: 0 }} /></div>
          <button type="submit">Consultar</button>
          <LimpiarFiltros activo={!!cod || !!desde || !!hasta}
                          onClear={() => { setCod(""); setDesde(""); setHasta(""); }} />
        </form>
        {error && <p className="error">{error}</p>}
      </div>

      {data && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>{data.cantidad} liquidaciones impagas — {money(data.total)}</h3>
          <div style={{ overflowX: "auto" }}>
            <table>
              <thead><tr><th>Agencia</th><th>Sub</th><th>Juego</th><th>N° Sorteo</th><th>Vto.</th><th>Días atr.</th><th>Moneda</th><th style={{ textAlign: "right" }}>Total</th><th style={{ textAlign: "right" }}>Total Gral.</th></tr></thead>
              <tbody>
                {data.items.map((it: any, i: number) => (
                  <tr key={i}>
                    <td>{it.cod_agencia || it.no_agencia}</td><td>{it.subagencia}</td>
                    <td>{it.juego}</td><td>{it.no_sorteo}</td>
                    <td>{it.fecha_vto || "-"}</td>
                    <td style={{ textAlign: "right", color: it.dias_atraso > 0 ? "var(--crit)" : undefined }}>{it.dias_atraso}</td>
                    <td style={{ textAlign: "center" }}>{it.moneda}</td>
                    <td style={{ textAlign: "right" }}>{money(it.total)}</td>
                    <td style={{ textAlign: "right" }}><b>{money(it.total_gral)}</b></td>
                  </tr>
                ))}
                {!data.items.length && <tr><td colSpan={9} className="muted">Sin deuda para esos filtros.</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  );
}
