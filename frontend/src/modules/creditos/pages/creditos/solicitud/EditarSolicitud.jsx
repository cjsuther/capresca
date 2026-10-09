import { useState } from "react";
import { creditos } from "../../../../../api/creditos";
import { Alerta, Boton, Field, Modal } from "../../../components/ui";
import { CampoCbu, CampoSueldo, CondicionesCredito, enRangoDe } from "./CondicionesCredito";

const RELACIONES = ["ESTANDAR", "PREFERENCIAL", "PREMIUM"];

/**
 * Corrige una solicitud en BORRADOR o EN_EVALUACION (también las del portal). El backend registra quién
 * la modificó, cuándo y qué cambió; si estaba en evaluación, las aprobaciones de la cadena se reinician.
 */
export function EditarSolicitud({ solicitud: s, lineas, segmentos = [], money, onGuardada, onClose }) {
  const da = s.datosAdicionales || {};
  const [f, setF] = useState({
    producto_id: s.productoId, monto: s.monto, plazo: s.plazo, segmento: s.segmento || "",
    fecha_nacimiento: s.fechaNacimiento || "", antiguedad_anios: s.antiguedadMeses == null ? "" : s.antiguedadMeses / 12,
    relacion: s.relacion || "ESTANDAR", sueldo: da.sueldo_declarado || "", cbu: da.cbu || "",
    observaciones: da.observaciones || "",
  });
  const [sim, setSim] = useState(null);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");
  const linea = lineas.find((l) => l.id === f.producto_id) || null;
  const set = (k) => (v) => setF((x) => ({ ...x, [k]: v }));
  const cbuDigitos = String(f.cbu).replace(/\D/g, "");
  const meses = f.antiguedad_anios === "" ? null : Math.round(Number(String(f.antiguedad_anios).replace(",", ".")) * 12);
  const listo = !!sim && sim.elegible !== false && (!cbuDigitos || cbuDigitos.length === 22);

  async function guardar() {
    setGuardando(true); setError("");
    try {
      const r = await creditos.ppSolicitudEditar(s.id, {
        producto_id: f.producto_id, monto_solicitado: Number(f.monto), plazo_solicitado: Number(f.plazo),
        segmento: f.segmento, relacion: f.relacion, observaciones: f.observaciones,
        sueldo: Number(f.sueldo) || 0, cbu: cbuDigitos,
        ...(f.fecha_nacimiento ? { fecha_nacimiento: f.fecha_nacimiento } : {}),
        ...(meses != null && !isNaN(meses) ? { antiguedad_meses: Math.max(0, meses) } : {}),
      });
      onGuardada(r);
    } catch (e) { setError(e.message); }
    finally { setGuardando(false); }
  }

  return (
    <Modal eyebrow={`${s.numero} · ${s.estado}`} titulo="Modificar solicitud" onClose={onClose}
           footer={<>
             <Boton variante="secundario" onClick={onClose} disabled={guardando}>Cancelar</Boton>
             <span className="flex-1" />
             <Boton onClick={guardar} disabled={guardando || !listo}>{guardando ? "Guardando…" : "Guardar cambios"}</Boton>
           </>}>
      {s.estado === "EN_EVALUACION" && (
        <div className="mb-3">
          <Alerta tipo="warn">Está en evaluación: al guardar, las aprobaciones que ya tuviera se reinician y se evalúa lo corregido.</Alerta>
        </div>
      )}
      {error && <div className="mb-3"><Alerta>{error}</Alerta></div>}

      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Línea">
          <select className="input w-full" value={f.producto_id} aria-label="Línea"
                  onChange={(e) => {
                    const l = lineas.find((x) => x.id === e.target.value);
                    setF((x) => ({ ...x, producto_id: e.target.value, ...enRangoDe(l, x.monto, x.plazo) }));
                  }}>
            {!linea && <option value={f.producto_id}>(línea actual)</option>}
            {lineas.map((l) => <option key={l.id} value={l.id}>{l.nombre} ({l.codigo})</option>)}
          </select>
        </Field>
        <CampoSueldo valor={f.sueldo} onChange={set("sueldo")} />
        <Field label="Fecha de nacimiento">
          <input type="date" className="input w-full" value={f.fecha_nacimiento} aria-label="Fecha de nacimiento"
                 max={new Date().toISOString().slice(0, 10)} onChange={(e) => set("fecha_nacimiento")(e.target.value)} />
        </Field>
        <Field label="Antigüedad laboral (años)">
          <input type="number" min={0} max={100} step="0.5" className="input w-full" value={f.antiguedad_anios}
                 aria-label="Antigüedad laboral" onChange={(e) => set("antiguedad_anios")(e.target.value)} />
        </Field>
        <Field label="Segmento">
          <select className="input w-full" value={f.segmento} onChange={(e) => set("segmento")(e.target.value)}>
            <option value="">(cualquiera)</option>
            {[...new Set([...segmentos, ...(f.segmento ? [f.segmento] : [])])].map((x) => <option key={x} value={x}>{x}</option>)}
          </select>
        </Field>
        <Field label="Relación">
          <select className="input w-full" value={f.relacion} onChange={(e) => set("relacion")(e.target.value)}>
            {RELACIONES.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
        </Field>
      </div>

      <div className="mt-4">
        <CondicionesCredito linea={linea} monto={Number(f.monto)} plazo={Number(f.plazo)} sueldo={f.sueldo} money={money}
                            onSim={setSim} onChange={({ monto, plazo }) => setF((x) => ({ ...x, monto, plazo }))}
                            perfil={{ segmento: f.segmento, canal: s.canal, fecha_nacimiento: f.fecha_nacimiento,
                                      antiguedad_meses: meses ?? "" }} />
      </div>

      <div className="grid gap-3 sm:grid-cols-2 mt-4">
        <CampoCbu valor={f.cbu} onChange={set("cbu")} />
        <Field label="Observaciones">
          <textarea rows={2} className="input w-full" value={f.observaciones} onChange={(e) => set("observaciones")(e.target.value)} />
        </Field>
      </div>
    </Modal>
  );
}
