import { useState } from "react";
import { api } from "../../api";

const money = (v: string | number) =>
  Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });

export default function Informes() {
  const [desde, setDesde] = useState("2026-01-01");
  const [hasta, setHasta] = useState("2026-12-31");
  const [cobrados, setCobrados] = useState<any>(null);
  const [primas, setPrimas] = useState<any>(null);

  async function ver() {
    setCobrados(await api.segurosCobrados(desde, hasta));
    setPrimas(await api.primasDevengadas(desde, hasta));
  }

  return (
    <div className="card">
      <h2 style={{ marginTop: 0 }}>Informes de seguros</h2>
      <div style={{ display: "flex", gap: "0.5rem", alignItems: "end", flexWrap: "wrap" }}>
        <div><label>Desde</label><input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} style={{ marginBottom: 0 }} /></div>
        <div><label>Hasta</label><input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} style={{ marginBottom: 0 }} /></div>
        <button onClick={ver}>Ver informes</button>
      </div>
      {(cobrados || primas) && (
        <div className="grid3" style={{ marginTop: "1rem" }}>
          {cobrados && <div><div className="kpi">{money(cobrados.total_seguro)}</div><div className="kpi-label">Seguros cobrados</div></div>}
          {primas && <div><div className="kpi">{money(primas.devengado)}</div><div className="kpi-label">Primas devengadas</div></div>}
          {primas && <div><div className="kpi">{money(primas.pendiente)}</div><div className="kpi-label">Primas pendientes</div></div>}
        </div>
      )}
    </div>
  );
}
