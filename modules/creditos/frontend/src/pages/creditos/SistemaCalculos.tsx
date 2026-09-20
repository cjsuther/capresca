import { useEffect, useState } from "react";
import { api } from "../../api";

type Sistema = {
  codigo: string; nombre: string; resumen: string; formula: string;
  variables: [string, string][]; pasos: string[]; nota: string;
};
type CalcCert = { sistema: string; version: number | null; estado: string; motor: string; checksumCert: string };
type Cert = {
  motor: string; certificado: boolean; checksum: string; checksumCorto: string;
  precisionDecimal: number; reglaRedondeo: string; lineasCodigo: number; fuenteUnica: string;
  calculadores: CalcCert[];
};
type PasoDebug = {
  cuota: number; saldoInicial: string; interes: string; capital: string;
  cuota_total: string; saldoFinal: string; enGracia: boolean; detalle: string[];
};

const SIS_LABEL: Record<string, string> = {
  FRANCES: "Francés", ALEMAN: "Alemán", AMERICANO: "Americano", BULLET: "Bullet",
};

export default function SistemaCalculos() {
  const [cat, setCat] = useState<{ sistemas: Sistema[]; reglasComunes: { titulo: string; detalle: string }[]; certificacion: Cert; gobernanza: string[] } | null>(null);
  const [sel, setSel] = useState("FRANCES");
  const [err, setErr] = useState("");

  // parámetros del depurador
  const [monto, setMonto] = useState(100000);
  const [plazo, setPlazo] = useState(6);
  const [tna, setTna] = useState(52);
  const [frecuencia, setFrecuencia] = useState("MENSUAL");
  const [gracia, setGracia] = useState(0);
  const [tipoCuota, setTipoCuota] = useState("VENCIDA");
  const [cargoPct, setCargoPct] = useState(0);

  const [dbg, setDbg] = useState<any>(null);
  const [expand, setExpand] = useState<number | null>(1);
  const [cargando, setCargando] = useState(false);

  useEffect(() => { api.sistemaCalculos().then(setCat).catch((e) => setErr(String(e))); }, []);

  useEffect(() => {
    const t = setTimeout(() => {
      setCargando(true);
      api.sistemaCalculosDebug({ sistema: sel, monto, plazo, tna, frecuencia, gracia, tipoCuota, cargoPct })
        .then((d) => { setDbg(d); setErr(""); })
        .catch((e) => setErr(String(e)))
        .finally(() => setCargando(false));
    }, 220);
    return () => clearTimeout(t);
  }, [sel, monto, plazo, tna, frecuencia, gracia, tipoCuota, cargoPct]);

  const sis = cat?.sistemas.find((s) => s.codigo === sel);
  const cert = cat?.certificacion;

  return (
    <div className="sc">
      <div className="sc-head">
        <div>
          <h1>Sistema de cálculos</h1>
          <p className="sc-sub">Cómo el motor arma cada cuota — fórmula aplicada, parámetros derivados y depuración paso a paso. Única fuente de verdad: el mismo código que la prueba en vivo, la simulación y la originación.</p>
        </div>
        {cert && (
          <div className="sc-cert" title={cert.checksum}>
            <span className="sc-badge">● motor certificado</span>
            <div className="sc-cert-grid">
              <span>checksum</span><b>{cert.checksumCorto}</b>
              <span>redondeo</span><b>{cert.reglaRedondeo}</b>
              <span>precisión</span><b>{cert.precisionDecimal} dec.</b>
              <span>fuente</span><b>{cert.motor}</b>
            </div>
          </div>
        )}
      </div>

      {err && <div className="sc-err">{err}</div>}

      <div className="sc-tabs">
        {(cat?.sistemas || []).map((s) => (
          <button key={s.codigo} className={sel === s.codigo ? "on" : ""} onClick={() => setSel(s.codigo)}>
            {SIS_LABEL[s.codigo] || s.codigo}
          </button>
        ))}
      </div>

      {sis && (
        <div className="sc-formula">
          <div className="sc-fx">
            <div className="sc-fx-title">{sis.nombre}</div>
            <p className="sc-fx-res">{sis.resumen}</p>
            <div className="sc-fx-eq">{sis.formula}</div>
            <div className="sc-fx-vars">
              {sis.variables.map(([k, d]) => (
                <div key={k}><code>{k}</code> <span>{d}</span></div>
              ))}
            </div>
          </div>
          <div className="sc-fx-pasos">
            <div className="sc-fx-title">Armado de cada cuota</div>
            <ol>{sis.pasos.map((p, i) => <li key={i}><code>{p}</code></li>)}</ol>
            {sis.nota && <p className="sc-nota">ℹ {sis.nota}</p>}
          </div>
        </div>
      )}

      <div className="sc-panel">
        <div className="sc-controls">
          <h3>Depurador de cuotas</h3>
          <label>Monto<input type="number" value={monto} onChange={(e) => setMonto(+e.target.value)} /></label>
          <label>Plazo (cuotas)<input type="number" value={plazo} onChange={(e) => setPlazo(+e.target.value)} /></label>
          <label>TNA %<input type="number" step="0.01" value={tna} onChange={(e) => setTna(+e.target.value)} /></label>
          <label>Frecuencia
            <select value={frecuencia} onChange={(e) => setFrecuencia(e.target.value)}>
              <option value="MENSUAL">Mensual</option>
              <option value="TRIMESTRAL">Trimestral</option>
            </select>
          </label>
          <label>Gracia (cuotas)<input type="number" value={gracia} onChange={(e) => setGracia(+e.target.value)} /></label>
          <label>Tipo cuota
            <select value={tipoCuota} onChange={(e) => setTipoCuota(e.target.value)}>
              <option value="VENCIDA">Vencida</option>
              <option value="ADELANTADA">Adelantada</option>
            </select>
          </label>
          <label>Cargo otorg. %<input type="number" step="0.01" value={cargoPct} onChange={(e) => setCargoPct(+e.target.value)} /></label>
          {cargando && <span className="sc-live">calculando…</span>}
        </div>

        <div className="sc-out">
          {dbg?.derivados && (
            <div className="sc-deriv">
              <div className="sc-fx-title">Parámetros derivados</div>
              {dbg.derivados.map((d: any) => (
                <div key={d.nombre} className="sc-deriv-row"><span>{d.nombre}</span><code>{d.valor}</code></div>
              ))}
            </div>
          )}

          {dbg?.resumen && (
            <div className="sc-rates">
              <div><span>TNA</span><b>{dbg.resumen.tna}%</b></div>
              <div><span>TEA</span><b>{dbg.resumen.tea}%</b></div>
              <div><span>CFT</span><b>{dbg.resumen.cft}%</b></div>
              <div><span>1ª cuota</span><b>${dbg.resumen.primeraCuota.toLocaleString("es-AR")}</b></div>
            </div>
          )}

          {dbg?.pasos && (
            <div className="sc-steps">
              <div className="sc-fx-title">Paso a paso (click para ver el detalle de cada cuota)</div>
              <table>
                <thead>
                  <tr><th>#</th><th>Saldo inicial</th><th>Interés</th><th>Capital</th><th>Cuota</th><th>Saldo final</th></tr>
                </thead>
                <tbody>
                  {dbg.pasos.map((p: PasoDebug) => (
                    <>
                      <tr key={p.cuota} className={"sc-row" + (expand === p.cuota ? " on" : "") + (p.enGracia ? " gracia" : "")}
                          onClick={() => setExpand(expand === p.cuota ? null : p.cuota)}>
                        <td>{p.cuota}{p.enGracia ? " ⟳" : ""}</td>
                        <td>{p.saldoInicial}</td>
                        <td>{p.interes}</td>
                        <td>{p.capital}</td>
                        <td><b>{p.cuota_total}</b></td>
                        <td>{p.saldoFinal}</td>
                      </tr>
                      {expand === p.cuota && (
                        <tr className="sc-detail-row"><td colSpan={6}>
                          <div className="sc-detail">
                            {p.detalle.map((l, i) => <div key={i} className="sc-detail-line">{l}</div>)}
                          </div>
                        </td></tr>
                      )}
                    </>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {cat?.reglasComunes && (
        <div className="sc-reglas">
          <div className="sc-fx-title">Reglas transversales (aplican sobre cualquier sistema)</div>
          <div className="sc-reglas-grid">
            {cat.reglasComunes.map((r) => (
              <div key={r.titulo} className="sc-regla"><b>{r.titulo}</b><span>{r.detalle}</span></div>
            ))}
          </div>
        </div>
      )}

      {cat?.gobernanza && cert && (
        <div className="sc-gob">
          <div className="sc-fx-title">Gobernanza — ¿cómo se “modifica” un cálculo?</div>
          <ul className="sc-gob-list">
            {cat.gobernanza.map((g, i) => <li key={i}>{g}</li>)}
          </ul>
          {cert.calculadores?.length > 0 && (
            <table className="sc-gob-table">
              <thead>
                <tr><th>Sistema</th><th>Calculador certificado</th><th>Versión</th><th>Estado</th><th>Motor</th></tr>
              </thead>
              <tbody>
                {cert.calculadores.map((c) => (
                  <tr key={c.sistema}>
                    <td>{SIS_LABEL[c.sistema] || c.sistema}</td>
                    <td><code>{c.checksumCert || "—"}</code></td>
                    <td>v{c.version ?? "—"}</td>
                    <td><span className={"sc-est " + (c.estado === "PUBLICADO" ? "ok" : "")}>{c.estado}</span></td>
                    <td>{c.motor || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
