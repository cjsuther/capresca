import { useEffect, useState } from "react";
import { api } from "../../api";
import LimpiarFiltros from "../../components/LimpiarFiltros";
import DataTable, { Col } from "../../components/DataTable";

const money = (v: string | number) =>
  Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });

const cols: Col[] = [
  { key: "nop", label: "N° OP" },
  { key: "fecha", label: "Fecha", render: (a) => a.fecha || "-" },
  { key: "vigencia", label: "Vigencia", render: (a) => a.vigencia || "-" },
  { key: "sistema", label: "Sistema" },
  { key: "resol", label: "Resol.", render: (a) => (a.nres1 ? `${a.nres1}${a.fres1 ? " · " + a.fres1 : ""}` : "-") },
  { key: "importe", label: "Importe", align: "right", render: (a) => money(a.importe) },
  { key: "importe_usado", label: "Usado", align: "right", render: (a) => money(a.importe_usado) },
  { key: "saldo", label: "Saldo", align: "right", render: (a) => <b>{money(a.saldo)}</b> },
  { key: "hab", label: "Hab.", render: (a) => (a.cancelada ? "Canc." : a.anulada ? "Anul." : a.habilitada ? "Sí" : "No") },
];

// Maestro de órdenes de pago = cupos autorizados (805100 / frm805100000altaop). Distinto
// del pago: cada OP es una autorización con importe autorizado, usado y saldo, vigencia y
// resolución. Los pagos consumen su saldo.
export default function AutorizacionesOP() {
  const [conSaldo, setConSaldo] = useState(true);
  const [soloHab, setSoloHab] = useState(true);
  const [q, setQ] = useState("");
  const [data, setData] = useState<any>({ items: [], total: 0 });
  const [tot, setTot] = useState<any>(null);
  const [offset, setOffset] = useState(0);
  const limit = 25;

  async function cargar() {
    const p: any = { con_saldo: conSaldo, q, limit, offset };
    if (soloHab) p.habilitada = true;
    setData(await api.autorizacionesOP(p));
    setTot(await api.autorizacionesOPTotales(soloHab ? true : undefined));
  }
  useEffect(() => { cargar(); /* eslint-disable-next-line */ }, [conSaldo, soloHab, offset]);

  return (
    <>
      <div className="card">
        <h2 style={{ marginTop: 0 }}>Órdenes de pago — cupos autorizados</h2>
        <p className="muted">Maestro de OP (805100): autorización con importe, usado, saldo, vigencia y resolución. Los pagos consumen el saldo.</p>
        {tot && (
          <div className="grid3">
            <div><div className="kpi">{tot.cantidad}</div><div className="kpi-label">Cupos</div></div>
            <div><div className="kpi">{money(tot.importe)}</div><div className="kpi-label">Autorizado</div></div>
            <div><div className="kpi">{money(tot.saldo)}</div><div className="kpi-label">Saldo</div></div>
          </div>
        )}
        <div style={{ display: "flex", gap: "1rem", alignItems: "end", flexWrap: "wrap", marginTop: "0.8rem" }}>
          <div><label>Buscar N° OP</label><input value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && (setOffset(0), cargar())} style={{ marginBottom: 0, width: 120 }} /></div>
          <label style={{ display: "flex", alignItems: "center", gap: "0.3rem" }}><input type="checkbox" checked={soloHab} onChange={(e) => { setOffset(0); setSoloHab(e.target.checked); }} style={{ width: "auto", margin: 0 }} /> Solo habilitadas</label>
          <label style={{ display: "flex", alignItems: "center", gap: "0.3rem" }}><input type="checkbox" checked={conSaldo} onChange={(e) => { setOffset(0); setConSaldo(e.target.checked); }} style={{ width: "auto", margin: 0 }} /> Con saldo</label>
          <button onClick={() => { setOffset(0); cargar(); }}>Buscar</button>
          <LimpiarFiltros activo={!!q || !soloHab || !conSaldo}
                          onClear={() => { setQ(""); setSoloHab(true); setConSaldo(true); setOffset(0); }} />
        </div>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>{data.total} cupos</h3>
        <DataTable columns={cols} rows={data.items} total={data.total} limit={limit} offset={offset}
                   onPage={setOffset} rowKey={(a) => a.id} emptyText="Sin cupos para el filtro." />
      </div>
    </>
  );
}
