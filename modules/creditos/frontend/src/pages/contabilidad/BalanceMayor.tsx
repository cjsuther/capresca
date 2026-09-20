import { useEffect, useState } from "react";
import { api } from "../../api";
import DataTable, { Col } from "../../components/DataTable";

const money = (v: string | number) =>
  Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });

const COLS_MAYOR: Col[] = [
  { key: "fecha", label: "Fecha", sortable: true, render: (m) => m.fecha || "-" },
  { key: "periodo", label: "Período", sortable: true },
  { key: "referencia", label: "Referencia", sortable: true },
  { key: "debito", label: "Débito", sortable: true, align: "right", sortValue: (m) => Number(m.debito), render: (m) => (Number(m.debito) ? money(m.debito) : "-") },
  { key: "credito", label: "Crédito", sortable: true, align: "right", sortValue: (m) => Number(m.credito), render: (m) => (Number(m.credito) ? money(m.credito) : "-") },
];

// Balance de sumas y saldos sobre el LIBRO MAYOR REAL (asientos migrados, ~2M
// movimientos). Al elegir una cuenta se ve su mayor (movimientos con débito/crédito).
export default function BalanceMayor() {
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [data, setData] = useState<any>(null);
  const [cuenta, setCuenta] = useState<string | null>(null);
  const [mayor, setMayor] = useState<any>(null);
  const [error, setError] = useState("");

  async function cargar(e?: React.FormEvent) {
    e?.preventDefault(); setError(""); setCuenta(null); setMayor(null);
    try { setData(await api.balanceMayor(desde, hasta)); }
    catch (err: any) { setError(err.message); }
  }
  useEffect(() => { cargar(); /* eslint-disable-next-line */ }, []);

  async function verMayor(c: string) {
    setCuenta(c);
    setMayor(await api.mayorCuenta(c, desde, hasta));
  }

  return (
    <>
      <div className="card">
        <h2 style={{ marginTop: 0 }}>Balance de sumas y saldos (mayor real)</h2>
        <p className="muted">Sobre el libro mayor real migrado (~2.000.000 de movimientos). Elegí una cuenta para ver su mayor.</p>
        <form onSubmit={cargar} style={{ display: "flex", gap: "0.5rem", alignItems: "end" }}>
          <div><label>Desde</label><input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} style={{ marginBottom: 0 }} /></div>
          <div><label>Hasta</label><input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} style={{ marginBottom: 0 }} /></div>
          <button type="submit">Filtrar</button>
        </form>
        {error && <p className="error">{error}</p>}
      </div>

      {data && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>{data.cantidad_cuentas} cuentas · Débito {money(data.total_debito)} · Crédito {money(data.total_credito)}</h3>
          <DataTable rows={data.cuentas} rowKey={(c) => c.cuenta}
                     rowStyle={(c) => (cuenta === c.cuenta ? { background: "var(--accent-soft)" } : undefined)}
                     actions={(c) => [{ label: "Ver mayor", icon: "eye", onClick: () => verMayor(c.cuenta) }]}
                     clientSort pageSize={50} defaultSort="cuenta"
                     columns={[
                       { key: "cuenta", label: "Cuenta", sortable: true, render: (c) => <b>{c.cuenta}</b> },
                       { key: "movimientos", label: "Movim.", sortable: true, align: "right" },
                       { key: "debito", label: "Débito", sortable: true, align: "right", sortValue: (c) => Number(c.debito), render: (c) => money(c.debito) },
                       { key: "credito", label: "Crédito", sortable: true, align: "right", sortValue: (c) => Number(c.credito), render: (c) => money(c.credito) },
                       { key: "saldo_deudor", label: "Saldo deudor", sortable: true, align: "right", sortValue: (c) => Number(c.saldo_deudor), render: (c) => money(c.saldo_deudor) },
                       { key: "saldo_acreedor", label: "Saldo acreedor", sortable: true, align: "right", sortValue: (c) => Number(c.saldo_acreedor), render: (c) => money(c.saldo_acreedor) },
                     ]} />
        </div>
      )}

      {mayor && cuenta && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Mayor de {cuenta} — {mayor.total.toLocaleString("es-AR")} movimientos · saldo {money(mayor.saldo)}</h3>
          <DataTable columns={COLS_MAYOR} rows={mayor.items} clientSort pageSize={50} defaultSort="fecha" />
          <p className="muted">El backend devolvió los primeros 200 (de {mayor.total.toLocaleString("es-AR")}).</p>
        </div>
      )}
    </>
  );
}
