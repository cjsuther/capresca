import { useEffect, useState } from "react";
import { api } from "../../api";
import { avisar } from "../../ui/dialog";

// Parámetros EXCLUSIVOS de créditos (H-197): catálogo de canales, canal del portal/backoffice y la
// cantidad de decimales para el redondeo de las cuotas en el cálculo de préstamos. Separados de los
// "Parámetros generales" (transversales) y de los contables.

const DESC: Record<string, string> = {
  CANALES: "Catálogo de canales de venta habilitados (coma-separado).",
  CANAL_PORTAL: "Código de canal habilitado en el portal del ciudadano (solo web).",
  CANAL_BACKOFFICE: "Canal asumido al originar desde el backoffice sin canal explícito.",
  DECIMALES_CALCULO: "Decimales para el REDONDEO del cálculo de las cuotas (0–6).",
  DECIMALES_MOSTRAR: "Decimales con que se MUESTRAN los importes de créditos en pantalla (0–6).",
};

export default function ParametrosCreditos() {
  const [canales, setCanales] = useState<string[]>([]);
  const [portal, setPortal] = useState("WEB");
  const [backoffice, setBackoffice] = useState("SUCURSAL");
  const [decimales, setDecimales] = useState(2);
  const [decimalesMostrar, setDecimalesMostrar] = useState(2);
  const [nuevoCanal, setNuevoCanal] = useState("");
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");

  async function cargar() {
    setError(""); setCargando(true);
    try {
      const ps: any[] = await api.adminParametros("creditos");
      const m: Record<string, string> = {};
      ps.forEach((p) => (m[p.clave] = p.valor));
      setCanales((m.CANALES || "SUCURSAL,WEB,APP,CONVENIO").split(",").map((s) => s.trim().toUpperCase()).filter(Boolean));
      setPortal((m.CANAL_PORTAL || "WEB").toUpperCase());
      setBackoffice((m.CANAL_BACKOFFICE || "SUCURSAL").toUpperCase());
      setDecimales(Math.max(0, Math.min(6, parseInt(m.DECIMALES_CALCULO || "2", 10) || 2)));
      setDecimalesMostrar(Math.max(0, Math.min(6, parseInt(m.DECIMALES_MOSTRAR || "2", 10) || 2)));
    } catch (e: any) { setError(e.message || String(e)); }
    finally { setCargando(false); }
  }
  useEffect(() => { cargar(); }, []);

  const agregarCanal = () => {
    const c = nuevoCanal.trim().toUpperCase();
    if (c && !canales.includes(c)) setCanales([...canales, c]);
    setNuevoCanal("");
  };
  const quitarCanal = (c: string) => {
    const nuevos = canales.filter((x) => x !== c);
    setCanales(nuevos);
    if (portal === c) setPortal(nuevos[0] || "");
    if (backoffice === c) setBackoffice(nuevos[0] || "");
  };

  async function guardar() {
    setError(""); setGuardando(true);
    try {
      const up = (clave: string, valor: string) => api.upsertParametro({ clave, valor, descripcion: DESC[clave] || "", ambito: "creditos" });
      await up("CANALES", canales.join(","));
      await up("CANAL_PORTAL", portal);
      await up("CANAL_BACKOFFICE", backoffice);
      await up("DECIMALES_CALCULO", String(Math.max(0, Math.min(6, decimales))));
      await up("DECIMALES_MOSTRAR", String(Math.max(0, Math.min(6, decimalesMostrar))));
      avisar({ tipo: "ok", mensaje: "Parámetros de créditos guardados." });
      cargar();
    } catch (e: any) { setError(e.message || String(e)); }
    finally { setGuardando(false); }
  }

  return (
    <div className="pcred">
      <div className="pcred-head">
        <div><h1 style={{ margin: 0 }}>Parámetros de créditos</h1>
          <p className="muted" style={{ margin: "2px 0 0" }}>Configuración exclusiva de créditos: canales de venta y decimales del cálculo. Separada de los Parámetros generales.</p></div>
      </div>
      {error && <div className="alert crit">{error}</div>}
      {cargando ? <p className="muted">Cargando…</p> : (
        <>
          <div className="card pcred-card">
            <h3>Canales de venta</h3>
            <p className="muted pcred-sub">Catálogo de canales por los que se ofrece un crédito. La disponibilidad por canal se define en cada línea (Configurar Créditos → Disponibilidad).</p>
            <div className="pcred-chips">
              {canales.map((c) => (
                <span className="pcred-chip" key={c}>{c}<button title="Quitar" onClick={() => quitarCanal(c)}>✕</button></span>
              ))}
              {canales.length === 0 && <span className="muted">Sin canales.</span>}
            </div>
            <div className="pcred-add">
              <input value={nuevoCanal} maxLength={20} placeholder="Nuevo canal (ej. TELEFONO)"
                onChange={(e) => setNuevoCanal(e.target.value.toUpperCase().replace(/[^A-Z0-9_]/g, ""))}
                onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); agregarCanal(); } }} />
              <button className="btn" onClick={agregarCanal} disabled={!nuevoCanal.trim()}>＋ Agregar</button>
            </div>
            <div className="pcred-grid">
              <label>Canal del portal (público)
                <select value={portal} onChange={(e) => setPortal(e.target.value)}>
                  {canales.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
                <small className="muted">Solo se ofrecen en el portal las líneas con este canal habilitado.</small>
              </label>
              <label>Canal del backoffice (por defecto)
                <select value={backoffice} onChange={(e) => setBackoffice(e.target.value)}>
                  {canales.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
                <small className="muted">Canal asumido al originar desde el backoffice sin elegir uno.</small>
              </label>
            </div>
          </div>

          <div className="card pcred-card">
            <h3>Cálculo de préstamos</h3>
            <div className="pcred-grid">
              <label>Decimales para el cálculo (redondeo)
                <input type="number" min={0} max={6} step={1} value={decimales}
                  onChange={(e) => setDecimales(Math.max(0, Math.min(6, Math.floor(Number(e.target.value) || 0))))} />
                <small className="muted">Precisión interna (0–6) con que el motor redondea cada cuota. Ej.: 4. Los contratos ya originados conservan su cronograma (snapshot); aplica a cálculos nuevos.</small>
              </label>
              <label>Decimales para mostrar
                <input type="number" min={0} max={6} step={1} value={decimalesMostrar}
                  onChange={(e) => setDecimalesMostrar(Math.max(0, Math.min(6, Math.floor(Number(e.target.value) || 0))))} />
                <small className="muted">Decimales (0–6) con que se presentan los importes en pantalla. Ej.: 2. No cambia el cálculo, sólo la visualización.</small>
              </label>
            </div>
          </div>

          <div className="pcred-foot">
            <button className="btn primary" onClick={guardar} disabled={guardando}>{guardando ? "Guardando…" : "Guardar parámetros"}</button>
          </div>
        </>
      )}

      <style>{`
        .pcred-head { margin-bottom:14px; }
        .pcred-card { margin-bottom:16px; }
        .pcred-card h3 { margin:0 0 4px; font-size:15px; }
        .pcred-sub { font-size:12.5px; margin:0 0 12px; }
        .pcred-chips { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:12px; }
        .pcred-chip { display:inline-flex; align-items:center; gap:6px; font-size:12.5px; font-weight:600; padding:5px 10px;
          border-radius:999px; background:var(--brand-soft, var(--surface-2)); color:var(--brand-2); border:1px solid var(--brand-2); }
        .pcred-chip button { border:0; background:transparent; color:inherit; cursor:pointer; font-size:12px; line-height:1; padding:0; }
        .pcred-add { display:flex; gap:8px; align-items:center; margin-bottom:16px; }
        .pcred-add input { margin:0; max-width:260px; }
        .pcred-grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(240px, 1fr)); gap:14px; }
        .pcred-grid label { display:flex; flex-direction:column; gap:4px; font-size:12.5px; font-weight:600; color:var(--ink-soft); }
        .pcred-grid input, .pcred-grid select { margin:0; }
        .pcred-grid small { font-weight:400; }
        .pcred-foot { display:flex; justify-content:flex-end; }
      `}</style>
    </div>
  );
}
