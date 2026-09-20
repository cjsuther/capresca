import { useEffect, useRef, useState } from "react";
import { api } from "../../api";
import { confirmar, avisar } from "../../ui/dialog";

const num = (v: any) => (v == null ? "—" : Number(v).toLocaleString("es-AR"));
const mb = (b: number | null) => (b == null ? "—" : `${(b / 1048576).toFixed(1)} MB`);

const JOB_PILL: Record<string, string> = { ok: "ok", corriendo: "warn", error: "crit" };

export default function Migradores() {
  const [data, setData] = useState<any>(null);
  const [abierto, setAbierto] = useState<string | null>(null);
  const [error, setError] = useState("");
  const timer = useRef<number | null>(null);

  async function cargar() {
    try { setData(await api.migradores()); }
    catch (e: any) { setError(e.message); }
  }
  useEffect(() => {
    cargar();
    timer.current = window.setInterval(cargar, 2500);
    return () => { if (timer.current) window.clearInterval(timer.current); };
  }, []);

  async function migrar(clave: string, reset: boolean) {
    const m = data.items.find((x: any) => x.clave === clave);
    if (reset && !(await confirmar({ titulo: "Re-migrar con reset", danger: true, mensaje: `Re-migrar "${m.nombre}" borra ${num(m.migrados)} registros de ${m.tabla} y recarga desde el DBF. ¿Continuar?` }))) return;
    try { await api.ejecutarMigrador(clave, reset); cargar(); }
    catch (e: any) { avisar({ tipo: "error", mensaje: e.message }); }
  }
  async function migrarTodo(reset: boolean) {
    if (!(await confirmar({ titulo: "Ejecutar todos los migradores", danger: reset, mensaje: `Ejecutar TODOS los migradores en orden${reset ? " con RESET (borra y recarga cada tabla)" : ""}. Puede tardar varios minutos. ¿Continuar?` }))) return;
    try { await api.ejecutarMigradoresTodo(reset); cargar(); }
    catch (e: any) { avisar({ tipo: "error", mensaje: e.message }); }
  }

  if (error) return <div className="card"><p className="error">{error}</p></div>;
  if (!data) return <div className="card"><p className="muted">Cargando catálogo…</p></div>;

  const todo = data.todo;

  return (
    <>
      <div className="card">
        <h1 style={{ marginTop: 0 }}>Migradores de datos (DBF → modelo)</h1>
        <p className="muted">
          Catálogo de migraciones del sistema legacy VFP al modelo actual. Cada migrador documenta el programa de origen,
          el archivo <code>.dbf</code>, la tabla destino y las conversiones. <b>Re-migrar</b> vuelve a cargar contra los DBF
          actualizados, para probar siempre con datos reales. Origen de los DBF: <code>{data.bases}</code>.
        </p>
        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
          <button className="btn-ghost" onClick={() => migrarTodo(false)}>▸ Ejecutar todos (faltantes)</button>
          <button onClick={() => migrarTodo(true)}>⟳ Re-migrar todo (reset)</button>
          {todo && <span className={`pill ${JOB_PILL[todo.estado] || "info"}`}>{todo.estado === "corriendo" ? "Migración total en curso…" : todo.mensaje}</span>}
        </div>
      </div>

      <div className="card" style={{ overflowX: "auto" }}>
        <table>
          <thead>
            <tr>
              <th>Módulo</th><th>Migrador</th><th>DBF de origen</th><th>Tabla</th>
              <th style={{ textAlign: "right" }}>Migrados</th><th>Estado</th><th></th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((m: any) => {
              const job = m.job;
              const corriendo = job?.estado === "corriendo";
              return (
                <>
                  <tr key={m.clave}>
                    <td>{m.modulo}</td>
                    <td>
                      <b>{m.nombre}</b>
                      <div className="muted" style={{ fontSize: 11 }}>{m.programa}</div>
                      <div style={{ fontSize: 10.5, marginTop: 3 }}>
                        {m.usos?.length
                          ? <span style={{ color: "var(--brand)" }}>Uso: {m.usos.map((u: any) => u.label).join(" · ")}</span>
                          : <span className="muted">Uso en menú: aún sin pantalla</span>}
                      </div>
                      <button className="btn-ghost" style={{ padding: "2px 8px", fontSize: 11, marginTop: 4 }}
                              onClick={() => setAbierto(abierto === m.clave ? null : m.clave)}>
                        {abierto === m.clave ? "▾ Conversiones" : `▸ Conversiones (${m.conversiones.length})`}
                      </button>
                    </td>
                    <td style={{ fontSize: 12 }}>
                      <code>{m.dbf}</code>
                      <div className={m.dbf_existe ? "muted" : "error"} style={{ fontSize: 11 }}>
                        {m.dbf_existe ? `✓ presente · ${mb(m.dbf_tamano)}` : "✗ no encontrado"}
                      </div>
                    </td>
                    <td><code>{m.tabla}</code></td>
                    <td style={{ textAlign: "right" }}>
                      {num(m.migrados)}
                      {m.esperado != null && <div className="muted" style={{ fontSize: 11 }}>de {num(m.esperado)}</div>}
                    </td>
                    <td>
                      {job ? <span className={`pill ${JOB_PILL[job.estado] || "info"}`}>{job.estado}</span> : <span className="muted">—</span>}
                      {job?.estado === "error" && <div className="error" style={{ fontSize: 11 }}>{job.mensaje}</div>}
                    </td>
                    <td style={{ whiteSpace: "nowrap", textAlign: "right" }}>
                      <button disabled={corriendo || !m.dbf_existe} onClick={() => migrar(m.clave, false)}
                              className="btn-ghost" style={{ padding: "5px 10px", marginRight: 4 }}>Migrar</button>
                      <button disabled={corriendo || !m.dbf_existe} onClick={() => migrar(m.clave, true)}
                              style={{ padding: "5px 10px" }}>⟳ Reset</button>
                    </td>
                  </tr>
                  {abierto === m.clave && (
                    <tr key={m.clave + "-conv"}>
                      <td colSpan={7} style={{ background: "var(--surface-2)" }}>
                        <table style={{ margin: 0 }}>
                          <thead><tr><th>Campo DBF</th><th>Campo del modelo</th><th>Tipo / nota</th></tr></thead>
                          <tbody>
                            {m.conversiones.map((c: any, i: number) => (
                              <tr key={i}><td><code>{c.origen}</code></td><td><code>{c.destino}</code></td><td className="muted">{c.tipo}</td></tr>
                            ))}
                          </tbody>
                        </table>
                      </td>
                    </tr>
                  )}
                </>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}
