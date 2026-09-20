import { useEffect, useState } from "react";
import { api } from "../../api";

const money = (v: string | number) =>
  Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });

// Anexo de Resolución — reconstruido del fuente VFP 120100000anexo_res_dis (H-026):
// se selecciona un TIPO (rango de líneas), se listan las solicitudes aprobadas sin
// resolución, se asignan a una resolución (lote = N° correlativo) y se imprime.
export default function Anexos() {
  const [tipos, setTipos] = useState<any[]>([]);
  const [tipo, setTipo] = useState(6);
  const [reimpLote, setReimpLote] = useState("");
  const [data, setData] = useState<any>({ items: [], total: 0, nombre: "" });
  const [sel, setSel] = useState<Record<number, boolean>>({});
  const [numero, setNumero] = useState("");
  const [fecha, setFecha] = useState(new Date().toISOString().slice(0, 10));
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");

  useEffect(() => { api.anexoTipos().then(setTipos); }, []);

  async function cargar(t = tipo, lote?: number) {
    setError(""); setOk(""); setSel({});
    setData(await api.anexoSolicitudes(t, lote));
  }
  useEffect(() => { cargar(tipo); }, [tipo]);

  const seleccionadas = data.items.filter((s: any) => sel[s.no_solicitud]);
  const totalSel = seleccionadas.reduce((a: number, s: any) => a + Number(s.montosol), 0);

  async function asignar() {
    setError(""); setOk("");
    try {
      const r = await api.anexoAsignar({
        tipo, numero: Number(numero), fecha,
        solicitud_ids: seleccionadas.map((s: any) => s.no_solicitud),
      });
      setOk(`${r.asignadas} solicitudes asignadas a la resolución N° ${r.numero} (total ${money(r.total)}).`);
      cargar(tipo);
      setNumero("");
    } catch (err: any) { setError(err.message); }
  }

  return (
    <>
      <div className="card">
        <h2 style={{ marginTop: 0 }}>Anexo de Resolución</h2>
        <p className="muted">Asigná un lote de solicitudes aprobadas a una resolución e imprimí el anexo. Fuente: solicitud (reconstruido del formulario VFP).</p>
        <div style={{ display: "flex", gap: "0.5rem", alignItems: "end", flexWrap: "wrap" }}>
          <div><label>Tipo de anexo</label>
            <select value={tipo} onChange={(e) => { setReimpLote(""); setTipo(Number(e.target.value)); }} style={{ marginBottom: 0 }}>
              {tipos.map((t) => <option key={t.tipo} value={t.tipo}>{t.nombre}</option>)}
            </select></div>
          <div><label>Reimpresión: N° de lote</label>
            <input value={reimpLote} onChange={(e) => setReimpLote(e.target.value)} style={{ marginBottom: 0, width: 120 }} /></div>
          <button onClick={() => cargar(tipo, reimpLote ? Number(reimpLote) : undefined)} style={{ background: "var(--ink-soft)" }}>Ver</button>
        </div>
      </div>

      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "0.5rem" }}>
          <h3 style={{ margin: 0 }}>Solicitudes {data.nombre && `(${data.nombre})`} — {Number(data.total).toLocaleString("es-AR", { style: "currency", currency: "ARS" })}</h3>
          {reimpLote && <button onClick={() => api.descargarAnexoExcel(tipo, Number(reimpLote))} style={{ background: "var(--ok)" }}>Descargar anexo (Excel)</button>}
        </div>
        <div style={{ overflowX: "auto", marginTop: "0.6rem" }}>
          <table>
            <thead><tr>{!reimpLote && <th></th>}<th>N° Sol.</th><th>Fecha</th><th>CUIL</th><th>Solicitante</th><th>Línea</th><th>Denominación</th><th style={{ textAlign: "right" }}>Capital</th></tr></thead>
            <tbody>
              {data.items.map((s: any) => (
                <tr key={s.no_solicitud}>
                  {!reimpLote && <td style={{ textAlign: "center" }}>
                    <input type="checkbox" style={{ width: "auto", margin: 0 }} checked={!!sel[s.no_solicitud]}
                           onChange={(e) => setSel({ ...sel, [s.no_solicitud]: e.target.checked })} /></td>}
                  <td>{s.no_solicitud}</td><td>{s.fecha_soli || "-"}</td><td>{s.cuil}</td>
                  <td>{s.apellido_nombre}</td><td>{s.linea}</td><td>{s.denominacion}</td>
                  <td style={{ textAlign: "right" }}>{money(s.montosol)}</td>
                </tr>
              ))}
              {!data.items.length && <tr><td colSpan={reimpLote ? 7 : 8} className="muted">Sin solicitudes pendientes para este tipo.</td></tr>}
            </tbody>
          </table>
        </div>

        {!reimpLote && data.items.length > 0 && (
          <div style={{ marginTop: "1rem", borderTop: "1px solid var(--borde)", paddingTop: "0.8rem" }}>
            <h4 style={{ marginTop: 0 }}>Asignar a resolución</h4>
            <div style={{ display: "flex", gap: "0.5rem", alignItems: "end", flexWrap: "wrap" }}>
              <div><label>N° correlativo</label><input value={numero} onChange={(e) => setNumero(e.target.value)} style={{ marginBottom: 0, width: 120 }} /></div>
              <div><label>Fecha</label><input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} style={{ marginBottom: 0 }} /></div>
              <button onClick={asignar} disabled={!seleccionadas.length || !numero}>
                Asignar {seleccionadas.length} · {money(totalSel)}
              </button>
            </div>
            {error && <p className="error">{error}</p>}
            {ok && <div className="aviso" style={{ marginTop: "0.6rem", borderColor: "var(--ok)", background: "var(--ok-soft)" }}>{ok}</div>}
          </div>
        )}
      </div>
    </>
  );
}
