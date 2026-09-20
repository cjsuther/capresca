import { useEffect, useState } from "react";
import { api } from "../../api";
import DataTable, { Col } from "../../components/DataTable";
import LimpiarFiltros from "../../components/LimpiarFiltros";

const COLS: Col[] = [
  { key: "tipo", label: "Tipo", sortable: true },
  { key: "descripcion", label: "Descripción", sortable: true },
  { key: "cantidad", label: "Cantidad", sortable: true, align: "right" },
];

export default function TramitesIngresados() {
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [data, setData] = useState<any>(null);

  async function cargar(d = desde, h = hasta) { setData(await api.tramitesIngresados(d, h)); }
  useEffect(() => { cargar(); }, []); // eslint-disable-line

  return (
    <div className="card">
      <h2 style={{ marginTop: 0 }}>Trámites ingresados</h2>
      <p className="muted">Cantidad de trámites ingresados por tipo (parte diario / informe de trámites ingresados).</p>
      <div style={{ display: "flex", gap: "0.5rem", alignItems: "end", flexWrap: "wrap", marginBottom: "0.8rem" }}>
        <div><label>Desde</label><input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} style={{ marginBottom: 0 }} /></div>
        <div><label>Hasta</label><input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} style={{ marginBottom: 0 }} /></div>
        <button onClick={() => cargar()}>Filtrar</button>
        <LimpiarFiltros activo={!!desde || !!hasta}
                        onClear={() => { setDesde(""); setHasta(""); cargar("", ""); }} />
        {data && <span className="kpi" style={{ marginLeft: "0.5rem" }}>{Number(data.total).toLocaleString("es-AR")} trámites</span>}
      </div>
      {data && (
        <div style={{ maxWidth: 560 }}>
          <DataTable columns={COLS} rows={data.por_tipo} rowKey={(f) => f.tipo}
                     clientSort defaultSort="cantidad" emptyText="Sin trámites en el período" />
        </div>
      )}
    </div>
  );
}
