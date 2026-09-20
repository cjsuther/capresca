import { useEffect, useMemo, useState } from "react";
import { api } from "../../api";
import { avisar } from "../../ui/dialog";

type Override = { id: string; username: string; modo: string };
type Nivel = { id: string; orden: number; nombre: string; rol: string; cuatroOjos: boolean; usuarios: Override[] };
type Regla = { id: string; objeto: string; nombre: string; descripcion: string; activo: boolean; niveles: Nivel[] };

const TRIGGER: Record<string, string> = {
  LINEA: "Se envía la versión a revisión", SOLICITUD: "Se envía la solicitud a evaluación",
  DESEMBOLSO: "Se solicita el desembolso", REFINANCIACION: "Se solicita refinanciar",
};
const FIN: Record<string, string> = {
  LINEA: "Versión publicada", SOLICITUD: "Solicitud aprobada",
  DESEMBOLSO: "Desembolso autorizado", REFINANCIACION: "Refinanciación autorizada",
};
const OBJ_LBL: Record<string, string> = {
  LINEA: "Línea de crédito", SOLICITUD: "Solicitud", DESEMBOLSO: "Desembolso", REFINANCIACION: "Refinanciación",
};

export default function WorkflowAprobaciones() {
  const [reglas, setReglas] = useState<Regla[]>([]);
  const [perfiles, setPerfiles] = useState<string[]>([]);
  const [puedeEditar, setPuede] = useState(false);
  const [objeto, setObjeto] = useState("LINEA");
  const [selNivel, setSelNivel] = useState<string | null>(null);
  const [err, setErr] = useState("");

  const cargar = () => api.wfListar().then((d) => {
    setReglas(d.reglas); setPerfiles(d.perfiles); setPuede(d.puedeEditar);
  }).catch((e) => setErr(e.message || String(e)));
  useEffect(() => { cargar(); }, []);

  const regla = useMemo(() => reglas.find((r) => r.objeto === objeto), [reglas, objeto]);
  const nivelSel = regla?.niveles.find((n) => n.id === selNivel) || null;
  const guard = (p: Promise<any>) => p.then(cargar).catch((e: any) => avisar({ tipo: "error", mensaje: e.message || String(e) }));

  return (
    <div className="wfa">
      <div className="wfa-head">
        <div>
          <h1 style={{ margin: 0 }}>Workflow de aprobaciones</h1>
          <p className="muted" style={{ margin: "2px 0 0" }}>Diseñá el circuito de aprobación por objeto: disparador → niveles en serie → fin.</p>
        </div>
        <span style={{ flex: 1 }} />
        {!puedeEditar && <span className="wfa-ro">Sólo lectura (requiere escritura de Seguridad en Portezuelo)</span>}
      </div>
      {err && <div className="alert crit">{err}</div>}

      <div className="wfa-tabs">
        {reglas.map((r) => (
          <button key={r.objeto} className={"wfa-tab" + (objeto === r.objeto ? " on" : "")}
                  onClick={() => { setObjeto(r.objeto); setSelNivel(null); }}>
            {OBJ_LBL[r.objeto] || r.objeto}
            {!r.activo && <span className="wfa-off">inactivo</span>}
          </button>
        ))}
      </div>

      {regla && (
        <div className="wfa-grid">
          {/* Lienzo del flujo */}
          <div className="wfa-canvas">
            <div className="wfa-rbar">
              <span className="muted" style={{ fontSize: 12.5 }}>{regla.descripcion}</span>
              <span style={{ flex: 1 }} />
              <label className="wfa-toggle" title={regla.activo ? "Exige aprobación" : "Sin aprobación"}>
                <input type="checkbox" checked={regla.activo} disabled={!puedeEditar}
                       onChange={(e) => guard(api.wfEditarRegla(regla.objeto, { activo: e.target.checked }))} />
                <span>{regla.activo ? "Activo" : "Inactivo"}</span>
              </label>
            </div>

            <Endpoint icon="play" cap="Disparador" txt={TRIGGER[objeto]} color="neutral" />
            <Link />
            {regla.niveles.map((n, i) => (
              <div key={n.id}>
                <div className={"wfa-node" + (selNivel === n.id ? " sel" : "")} onClick={() => setSelNivel(n.id)}>
                  <div className="wfa-nhead">
                    <span className="wfa-cap">Nivel {i + 1}</span>
                    <b style={{ fontSize: 14 }}>{n.nombre}</b>
                    {n.cuatroOjos && <span className="wfa-chip warn">cuatro-ojos</span>}
                    <span style={{ flex: 1 }} />
                    {puedeEditar && regla.niveles.length > 1 &&
                      <button className="wfa-x" title="Quitar nivel" onClick={(e) => { e.stopPropagation(); guard(api.wfBorrarNivel(n.id)); }}>×</button>}
                  </div>
                  <div className="wfa-chips">
                    <span className="wfa-chip">aprueba rol {n.rol}</span>
                  </div>
                </div>
                <Link />
              </div>
            ))}
            {puedeEditar &&
              <>
                <button className="wfa-add" onClick={() => guard(api.wfAgregarNivel(regla.objeto, { nombre: "Aprobación", rol: perfiles[0] || "APROBAR", cuatroOjos: true }))}>
                  ＋ Agregar nivel en serie
                </button>
                <Link />
              </>}
            <Endpoint icon="flag-check" cap="Fin" txt={FIN[objeto]} color="success" />
          </div>

          {/* Inspector del nivel seleccionado */}
          <div className="wfa-insp">
            {!nivelSel && <div className="muted" style={{ fontSize: 13, padding: "8px 0" }}>Elegí un nivel del flujo para configurarlo.</div>}
            {nivelSel && (
              <div className="wfa-inspcard">
                <div className="wfa-cap" style={{ marginBottom: 10 }}>Configurar nivel</div>
                <label className="wfa-lbl">Nombre</label>
                <input defaultValue={nivelSel.nombre} disabled={!puedeEditar}
                       onBlur={(e) => e.target.value !== nivelSel.nombre && guard(api.wfEditarNivel(nivelSel.id, { nombre: e.target.value, rol: nivelSel.rol, cuatroOjos: nivelSel.cuatroOjos }))} />
                <label className="wfa-lbl">Rol que aprueba</label>
                <select value={nivelSel.rol} disabled={!puedeEditar}
                        onChange={(e) => guard(api.wfEditarNivel(nivelSel.id, { nombre: nivelSel.nombre, rol: e.target.value, cuatroOjos: nivelSel.cuatroOjos }))}>
                  {perfiles.map((p) => <option key={p} value={p}>{p}</option>)}
                </select>
                <label className="wfa-chkline">
                  <input type="checkbox" checked={nivelSel.cuatroOjos} disabled={!puedeEditar}
                         onChange={(e) => guard(api.wfEditarNivel(nivelSel.id, { nombre: nivelSel.nombre, rol: nivelSel.rol, cuatroOjos: e.target.checked }))} />
                  Cuatro-ojos <small className="muted">(no aprueba quien ya intervino)</small>
                </label>

                <div className="wfa-note">
                  <b>¿Quién puede aprobar este paso?</b> Todo usuario que tenga el permiso{" "}
                  <b>creditos:aprobaciones:{nivelSel.rol.toLowerCase()}</b> en <b>Seguridad de Portezuelo</b>
                  (directo o por uno de sus roles). Para habilitar a alguien, asignale ese permiso allá — no se
                  configura por excepciones acá.
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      <style>{`
        .wfa-head { display:flex; align-items:flex-start; gap:10px; margin-bottom:14px; }
        .wfa-ro { font-size:.72rem; color:var(--ink-soft); border:1px solid var(--border); border-radius:999px; padding:3px 10px; }
        .wfa-tabs { display:flex; gap:6px; flex-wrap:wrap; margin-bottom:14px; }
        .wfa-tab { display:flex; align-items:center; gap:6px; padding:7px 14px; border:1px solid var(--border); border-radius:999px; background:var(--surface); color:var(--ink-soft); font:inherit; font-size:13px; cursor:pointer; }
        .wfa-tab.on { border-color:var(--brand-2); background:color-mix(in srgb, var(--brand-2) 12%, transparent); color:var(--brand-2); font-weight:600; }
        .wfa-off { font-size:10px; text-transform:uppercase; letter-spacing:.3px; opacity:.6; }
        .wfa-grid { display:grid; grid-template-columns:minmax(0,1fr) 260px; gap:16px; align-items:start; }
        .wfa-canvas { display:flex; flex-direction:column; }
        .wfa-rbar { display:flex; align-items:center; gap:10px; margin-bottom:10px; }
        .wfa-toggle { display:flex; align-items:center; gap:6px; font-size:.82rem; color:var(--ink-soft); cursor:pointer; }
        .wfa-ep { display:flex; gap:10px; align-items:center; border:1px solid var(--border); border-radius:12px; background:var(--surface); padding:11px 13px; }
        .wfa-epc { width:30px; height:30px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:14px; }
        .wfa-node { border:1px solid var(--border); border-radius:12px; background:var(--surface); padding:12px 14px; cursor:pointer; }
        .wfa-node.sel { border:2px solid var(--brand-2); padding:11px 13px; }
        .wfa-nhead { display:flex; align-items:center; gap:8px; margin-bottom:8px; }
        .wfa-cap { font-size:11px; text-transform:uppercase; letter-spacing:.4px; color:var(--ink-faint); }
        .wfa-chips { display:flex; gap:6px; flex-wrap:wrap; }
        .wfa-chip { font-size:12px; border-radius:999px; padding:2px 9px; background:var(--accent-soft); color:var(--brand-2); }
        .wfa-chip.incluir { background:var(--ok-soft); color:var(--ok); } .wfa-chip.excluir { background:var(--crit-soft); color:var(--crit); }
        .wfa-chip.warn { background:var(--warn-soft); color:var(--warn); }
        .wfa-link { display:flex; justify-content:center; color:var(--ink-faint); height:20px; align-items:center; }
        .wfa-add { border:1px dashed var(--border-strong, var(--border)); border-radius:12px; padding:10px; text-align:center; color:var(--ink-soft); font-size:13px; cursor:pointer; background:transparent; }
        .wfa-x { border:none; background:transparent; color:var(--ink-faint); cursor:pointer; font-size:16px; padding:0 3px; }
        .wfa-insp { position:sticky; top:12px; }
        .wfa-inspcard { background:var(--surface-2); border:1px solid var(--border); border-radius:12px; padding:14px; }
        .wfa-lbl { display:block; font-size:12px; color:var(--ink-soft); margin:8px 0 4px; }
        .wfa-chkline { display:flex; align-items:center; gap:8px; font-size:13px; margin:12px 0; cursor:pointer; }
        .wfa-note { margin-top:12px; font-size:12.5px; line-height:1.5; color:var(--ink-soft); background:var(--accent-soft); border:1px solid var(--border); border-radius:10px; padding:10px 12px; }
        .wfa-insp input, .wfa-insp select { width:100%; }
      `}</style>
    </div>
  );
}

function Link() { return <div className="wfa-link">↓</div>; }

function Endpoint({ icon, cap, txt, color }: { icon: string; cap: string; txt: string; color: string }) {
  const bg = color === "success" ? "var(--ok-soft)" : "var(--surface-2)";
  const fg = color === "success" ? "var(--ok)" : "var(--ink-soft)";
  return (
    <div className="wfa-ep">
      <span className="wfa-epc" style={{ background: bg, color: fg }}>{icon === "play" ? "▶" : "✓"}</span>
      <div><div className="wfa-cap">{cap}</div><div style={{ fontSize: 14 }}>{txt}</div></div>
    </div>
  );
}

