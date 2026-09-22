import { useEffect, useMemo, useState } from "react";
import { X } from "lucide-react";
import { PageHeader, Card, Field, Alerta, Boton, Modal } from "../../../components/ui";
import { Pill } from "../../../components/ui/Pill";
import { Confirmacion } from "../../../components/ui/Confirmacion";
import {
  listarWorkflow, editarRegla, agregarNivel, editarNivel, borrarNivel, agregarOverride, borrarOverride, mensajeDeError,
} from "../../../api/configuraciones";

const MODULOS = { creditos: "Créditos" };
const ROLES = {
  APROBAR: "Aprobador (permiso aprobaciones:aprobar)",
  SUPERVISAR: "Supervisor (permiso aprobaciones:supervisar)",
};

/**
 * Reglas de aprobación de cada módulo: niveles en serie, quién aprueba cada uno (rol de Seguridad más
 * excepciones por usuario) y cuatro-ojos. Quién puede editar lo decide `puedeEditar` que devuelve la
 * API (permiso configuraciones:workflow:write).
 */
export default function WorkflowPage() {
  const [data, setData] = useState({ reglas: [], roles: [], puedeEditar: false });
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [nivelForm, setNivelForm] = useState(null);        // { reglaId, id?, nombre, rol, cuatroOjos }
  const [overrideForm, setOverrideForm] = useState(null);  // { nivel, username, modo }
  const [confirmar, setConfirmar] = useState(null);        // { titulo, mensaje, confirmar, danger, accion }
  const [errModal, setErrModal] = useState("");
  const editar = data.puedeEditar;

  const cargar = () =>
    listarWorkflow()
      .then((d) => { setData(d); setError(""); })
      .catch((e) => setError(mensajeDeError(e, "No se pudo cargar el workflow")))
      .finally(() => setCargando(false));
  useEffect(() => { cargar(); }, []);

  const porModulo = useMemo(() => {
    const g = {};
    data.reglas.forEach((r) => { (g[r.modulo] ||= []).push(r); });
    return Object.entries(g);
  }, [data.reglas]);

  /** Ejecuta un cambio y recarga; los errores van al modal abierto o al aviso general. */
  async function aplicar(fn, { enModal = false } = {}) {
    setErrModal("");
    try {
      await fn();
      setNivelForm(null); setOverrideForm(null); setConfirmar(null);
      await cargar();
    } catch (e) {
      if (enModal) setErrModal(mensajeDeError(e));
      else { setError(mensajeDeError(e)); setConfirmar(null); }
    }
  }

  const pedirCambioEstado = (r) => setConfirmar(r.activo ? {
    titulo: "Desactivar la regla",
    mensaje: `${r.nombre}\nDeja de exigirse la aprobación: la operación se ejecuta con el permiso de aprobar de la pantalla, sin cuatro-ojos.`,
    confirmar: "Desactivar", danger: true, accion: () => editarRegla(r.id, { activo: false }),
  } : {
    titulo: "Activar la regla",
    mensaje: `${r.nombre}\nDesde ahora la operación queda pendiente hasta completar los ${r.niveles.length} nivel(es) de aprobación.`,
    confirmar: "Activar", danger: false, accion: () => editarRegla(r.id, { activo: true }),
  });

  return (
    <>
      <PageHeader titulo="Workflow de aprobaciones"
                  descripcion="Qué operaciones exigen aprobación, en cuántos niveles y quién aprueba cada uno. Los roles salen de los permisos de Seguridad; cuatro-ojos impide aprobar algo en lo que ya se intervino." />

      {error && <div className="mb-4"><Alerta>{error}</Alerta></div>}
      {!editar && !cargando && (
        <div className="mb-4"><Alerta tipo="warn">Sólo lectura: configurar el workflow requiere el permiso configuraciones:workflow:write.</Alerta></div>
      )}
      {cargando && <Card>Cargando…</Card>}

      {porModulo.map(([modulo, reglas]) => (
        <section key={modulo} className="mb-6">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500 mb-2">{MODULOS[modulo] || modulo}</h2>
          <div className="grid gap-4">
            {reglas.map((r) => (
              <Card key={r.id} padding={false}>
                <div className="flex flex-wrap items-start gap-3 px-4 py-3 border-b border-gray-200">
                  <div className="min-w-0">
                    <h3 className="font-semibold text-gray-800">{r.nombre}</h3>
                    <p className="text-sm text-gray-500">{r.descripcion}</p>
                  </div>
                  <span className="flex-1" />
                  <Pill tono={r.activo ? "ok" : "neutral"}>{r.activo ? "Activa" : "Inactiva"}</Pill>
                  {editar && (
                    <Boton variante={r.activo ? "secundario" : "primario"} onClick={() => pedirCambioEstado(r)}>
                      {r.activo ? "Desactivar" : "Activar"}
                    </Boton>
                  )}
                </div>

                <ol aria-label={`Niveles de ${r.nombre}`} className="divide-y divide-gray-100">
                  {r.niveles.map((n) => (
                    <li key={n.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
                      <span className="w-7 h-7 rounded-full bg-blue-50 text-blue-700 text-sm font-semibold flex items-center justify-center shrink-0">
                        {n.orden}
                      </span>
                      <div className="min-w-0">
                        <p className="font-medium text-gray-800">{n.nombre}</p>
                        <p className="text-xs text-gray-500">
                          {ROLES[n.rol] || n.rol}{n.cuatroOjos ? " · cuatro-ojos" : " · sin cuatro-ojos"}
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {n.usuarios.map((u) => (
                          <span key={u.id} className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full ${
                            u.modo === "INCLUIR" ? "bg-green-100 text-green-700" : "bg-red-100 text-red-600"}`}>
                            {u.modo === "INCLUIR" ? "+" : "−"} {u.username}
                            {editar && (
                              <button aria-label={`Quitar ${u.username}`} onClick={() => aplicar(() => borrarOverride(u.id))}
                                      className="hover:opacity-70"><X size={12} /></button>
                            )}
                          </span>
                        ))}
                      </div>
                      <span className="flex-1" />
                      {editar && (
                        <div className="flex gap-3 text-sm">
                          <button className="text-blue-600 hover:underline"
                                  onClick={() => { setErrModal(""); setOverrideForm({ nivel: n, username: "", modo: "INCLUIR" }); }}>
                            Excepción
                          </button>
                          <button className="text-blue-600 hover:underline"
                                  onClick={() => { setErrModal(""); setNivelForm({ reglaId: r.id, ...n }); }}>
                            Editar
                          </button>
                          {r.niveles.length > 1 && (
                            <button className="text-red-600 hover:underline" onClick={() => setConfirmar({
                              titulo: "Quitar nivel", confirmar: "Quitar", danger: true,
                              mensaje: `Nivel ${n.orden} · ${n.nombre}\nLos niveles siguientes se renumeran.`,
                              accion: () => borrarNivel(n.id),
                            })}>Quitar</button>
                          )}
                        </div>
                      )}
                    </li>
                  ))}
                </ol>
                {editar && (
                  <div className="px-4 py-3 border-t border-gray-200">
                    <button className="text-sm text-blue-600 hover:underline"
                            onClick={() => { setErrModal(""); setNivelForm({ reglaId: r.id, nombre: "", rol: "APROBAR", cuatroOjos: true }); }}>
                      ＋ Agregar nivel
                    </button>
                  </div>
                )}
              </Card>
            ))}
          </div>
        </section>
      ))}

      {nivelForm && (
        <Modal titulo={nivelForm.id ? `Editar nivel ${nivelForm.orden}` : "Nuevo nivel"} eyebrow="Workflow"
               onClose={() => setNivelForm(null)} ancho="max-w-lg"
               footer={<>
                 <span className="flex-1" />
                 <Boton variante="secundario" onClick={() => setNivelForm(null)}>Cancelar</Boton>
                 <Boton onClick={() => {
                   const d = { nombre: nivelForm.nombre, rol: nivelForm.rol, cuatroOjos: nivelForm.cuatroOjos };
                   aplicar(() => (nivelForm.id ? editarNivel(nivelForm.id, d) : agregarNivel(nivelForm.reglaId, d)), { enModal: true });
                 }} disabled={!nivelForm.nombre.trim()}>Guardar</Boton>
               </>}>
          <div className="grid gap-3">
            {errModal && <Alerta>{errModal}</Alerta>}
            <Field label="Nombre del nivel">
              <input className="input" maxLength={60} value={nivelForm.nombre} placeholder="p.ej. Gerencia"
                     onChange={(e) => setNivelForm((f) => ({ ...f, nombre: e.target.value }))} />
            </Field>
            <Field label="Aprueba">
              <select className="input" value={nivelForm.rol} onChange={(e) => setNivelForm((f) => ({ ...f, rol: e.target.value }))}>
                {(data.roles.length ? data.roles : Object.keys(ROLES)).map((r) => <option key={r} value={r}>{ROLES[r] || r}</option>)}
              </select>
            </Field>
            <label className="flex items-center gap-2 text-sm text-gray-600">
              <input type="checkbox" checked={nivelForm.cuatroOjos}
                     onChange={(e) => setNivelForm((f) => ({ ...f, cuatroOjos: e.target.checked }))} />
              Cuatro-ojos: no puede aprobar quien envió la operación ni quien aprobó un nivel anterior
            </label>
          </div>
        </Modal>
      )}

      {overrideForm && (
        <Modal titulo={`Excepción en «${overrideForm.nivel.nombre}»`} eyebrow="Workflow" onClose={() => setOverrideForm(null)} ancho="max-w-lg"
               footer={<>
                 <span className="flex-1" />
                 <Boton variante="secundario" onClick={() => setOverrideForm(null)}>Cancelar</Boton>
                 <Boton disabled={!overrideForm.username.trim()} onClick={() => aplicar(
                   () => agregarOverride(overrideForm.nivel.id, { username: overrideForm.username, modo: overrideForm.modo }),
                   { enModal: true })}>Guardar</Boton>
               </>}>
          <div className="grid gap-3">
            {errModal && <Alerta>{errModal}</Alerta>}
            <Field label="Usuario (como figura en Seguridad)">
              <input className="input" maxLength={60} value={overrideForm.username}
                     onChange={(e) => setOverrideForm((f) => ({ ...f, username: e.target.value }))} />
            </Field>
            <Field label="Excepción">
              <select className="input" value={overrideForm.modo} onChange={(e) => setOverrideForm((f) => ({ ...f, modo: e.target.value }))}>
                <option value="INCLUIR">Incluir: aprueba este nivel aunque no tenga el rol</option>
                <option value="EXCLUIR">Excluir: no aprueba este nivel aunque tenga el rol</option>
              </select>
            </Field>
          </div>
        </Modal>
      )}

      {confirmar && (
        <Confirmacion titulo={confirmar.titulo} mensaje={confirmar.mensaje} confirmar={confirmar.confirmar}
                      danger={confirmar.danger} onConfirmar={() => aplicar(confirmar.accion)}
                      onCancelar={() => setConfirmar(null)} />
      )}
    </>
  );
}
