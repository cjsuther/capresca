import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../../api";
import VolverFicha from "../../components/VolverFicha";
import DataTable, { Col } from "../../components/DataTable";

const money = (v: string | number) =>
  Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });

const TIPO: Record<string, string> = {
  D: "Débito", C: "Crédito", O: "Otorgamiento", P: "Pago", A: "Ajuste",
};

// Los importes NO son ordenables: la columna Saldo es un saldo corrido (cronológico).
const COLS: Col[] = [
  { key: "fecha", label: "Fecha", sortable: true, render: (m) => m.fecha || "-" },
  { key: "cuota", label: "Cuota", sortable: true, align: "right", render: (m) => m.cuota || "-" },
  { key: "tipo", label: "Tipo", render: (m) => TIPO[m.tipo] || m.tipo || "-" },
  { key: "no_recibo", label: "Recibo", render: (m) => m.no_recibo || "-" },
  { key: "debitos", label: "Débitos", align: "right", render: (m) => money(m.debitos) },
  { key: "creditos", label: "Créditos", align: "right", render: (m) => money(m.creditos) },
  { key: "capital", label: "Capital", align: "right", render: (m) => money(m.capital) },
  { key: "interes", label: "Interés", align: "right", render: (m) => money(m.interes) },
  { key: "iva", label: "IVA", align: "right", render: (m) => money(m.iva) },
  { key: "punitorio", label: "Punit.", align: "right", render: (m) => money(m.punitorio) },
  { key: "saldo", label: "Saldo", align: "right", render: (m) => <b>{money(m.saldo)}</b> },
];

export default function CuentaCorriente() {
  const [params] = useSearchParams();
  const [creditoId, setCreditoId] = useState(params.get("credito") || "");
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");

  async function buscar(e?: React.FormEvent, valor?: string) {
    e?.preventDefault(); setError("");
    const id = Number(valor ?? creditoId);
    if (!id) { setError("Ingresá un número de crédito."); setData(null); return; }
    try { setData(await api.cuentaCorriente(id)); }
    catch (err: any) { setError(err.message); setData(null); }
  }
  useEffect(() => {
    const p = params.get("credito");
    if (p) buscar(undefined, p);
  }, []); // eslint-disable-line

  return (
    <>
      <VolverFicha />
      <div className="card">
      <h2 style={{ marginTop: 0 }}>Cuenta corriente del crédito</h2>
      <p className="muted">Movimientos (débitos/créditos) de un crédito con saldo corrido. Fuente: ctacte.</p>
      <form onSubmit={buscar} style={{ display: "flex", gap: "0.5rem", alignItems: "end", marginBottom: "0.8rem" }}>
        <div><label>N° de crédito</label><input value={creditoId} onChange={(e) => setCreditoId(e.target.value)} style={{ marginBottom: 0 }} /></div>
        <button type="submit">Ver cuenta corriente</button>
      </form>
      {error && <p className="error">{error}</p>}
      {data && (
        <>
          <p className="muted">
            <b>{Number(data.cantidad).toLocaleString("es-AR")}</b> movimientos · saldo final <b>{money(data.saldo_final)}</b>
          </p>
          <DataTable columns={COLS} rows={data.movimientos} pageSize={50}
                     emptyText="El crédito no tiene movimientos en cuenta corriente." />
        </>
      )}
    </div>
    </>
  );
}
