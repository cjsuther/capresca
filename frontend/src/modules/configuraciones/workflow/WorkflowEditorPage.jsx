import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { GitCompare } from "lucide-react";
import { Alerta, Boton, Card, Field, Modal } from "../../../components/ui";
import { Pill } from "../../../components/ui/Pill";
import { Confirmacion } from "../../../components/ui/Confirmacion";
import {
  compararVersiones, crearBorrador, descartarBorrador, guardarBorrador, habilitarProceso, listarProcesos, mensajeDeError,
  problemasDeError, publicarVersion, retirarVersion, verProceso, verVersion,
} from "../../../api/configuraciones";
import EditorWorkflow from "./EditorWorkflow";
import { cantidadAprobaciones, errores, motivosIncompatible, validar } from "./grafo";
import { marcasDiff } from "./flow";
import { cargarPersonas } from "./personas";

const MODULOS = { creditos: "Créditos", tesoreria: "Tesorería" };
const TONO_ESTADO = { PUBLICADA: "ok", BORRADOR: "warn", RETIRADA: "neutral" };
const AUTOSAVE_MS = 1200;

const fecha = (iso) => (iso ? new Date(iso).toLocaleString("es-AR", { dateStyle: "short", timeStyle: "short" }) : "");

/**
 * Editor gráfico del workflow de aprobaciones: procesos a la izquierda, diagrama de la versión elegida,
 * borrador con autosave, publicación (permiso workflow:publish + doble factor) y comparación de versiones.
 */
export default function WorkflowEditorPage() {
  const [procesos, setProcesos] = useState([]);
  const [puede, setPuede] = useState({ editar: false, publicar: false });
  const [procesoId, setProcesoId] = useState(null);
  const [proceso, setProceso] = useState(null);
  const [version, setVersion] = useState(null);
  const [edicion, setEdicion] = useState(null);           // {grafo, layout} que se ve y se edita
  const [guardado, setGuardado] = useState("");           // "" | pendiente | guardando | guardado | conflicto | error
  const [personas, setPersonas] = useState({ grupos: [], usuarios: [], deSeguridad: false });
  const [error, setError] = useState("");
  const [cargando, setCargando] = useState(true);
  const [modal, setModal] = useState(null);               // {tipo: publicar|retirar|descartar|habilitar, ...}
  const [comparacion, setComparacion] = useState(null);   // {contra, diff}
  const timer = useRef(null);
  const pendiente = useRef(null);                       // {grafo, layout} sin guardar
  const revision = useRef(0);                           // última revisión confirmada por el servidor
  const cadena = useRef(Promise.resolve(true));

  const recargarProcesos = useCallback(() => listarProcesos().then((d) => {
    setProcesos(d.procesos); setPuede(d.puede);
    setProcesoId((actual) => actual ?? d.procesos[0]?.id ?? null);
  }), []);

  useEffect(() => {
    recargarProcesos().catch((e) => setError(mensajeDeError(e, "No se pudo cargar el workflow"))).finally(() => setCargando(false));
    cargarPersonas().then(setPersonas).catch(() => {});
  }, [recargarProcesos]);

  const abrirVersion = useCallback(async (vid) => {
    const v = await verVersion(vid);
    setVersion(v);
    setEdicion({ grafo: v.grafo, layout: v.layout });
    revision.current = v.revision;
    pendiente.current = null;
    setGuardado("");
    setComparacion(null);
  }, []);

  const cargarProceso = useCallback(async (pid, preferida = null) => {
    const p = await verProceso(pid);
    setProceso(p);
    const vid = preferida ?? p.borrador?.id ?? p.publicada?.id ?? p.versiones?.[0]?.id;
    if (vid) await abrirVersion(vid);
    else { setVersion(null); setEdicion(null); }
  }, [abrirVersion]);

  useEffect(() => {
    if (procesoId == null) return;
    cargarProceso(procesoId).catch((e) => setError(mensajeDeError(e)));
  }, [procesoId, cargarProceso]);

  const esBorrador = version?.estado === "BORRADOR";
  const soloLectura = !esBorrador || !puede.editar || guardado === "conflicto";
  const variables = proceso?.variables || {};
  const problemas = useMemo(() => (edicion ? validar(edicion.grafo, variables) : []), [edicion, variables]);
  const incompatibles = useMemo(() => (edicion ? motivosIncompatible(edicion.grafo) : []), [edicion]);

  // ── Autosave del borrador ──
  // Los guardados van en cadena (nunca dos a la vez) y siempre con la última revisión que confirmó el
  // servidor: así un guardado lento no provoca un falso «otro usuario cambió el borrador».
  const guardarYa = useCallback(() => {
    clearTimeout(timer.current);
    cadena.current = cadena.current.then(async () => {
      const datos = pendiente.current;
      if (!datos || !version) return true;
      pendiente.current = null;
      setGuardado("guardando");
      try {
        const v = await guardarBorrador(version.id, { ...datos, revision: revision.current });
        revision.current = v.revision;
        setGuardado(pendiente.current ? "pendiente" : "guardado");
        return true;
      } catch (e) {
        const conflicto = e?.response?.status === 409;
        setGuardado(conflicto ? "conflicto" : "error");
        setError(mensajeDeError(e, "No se pudo guardar el borrador"));
        return false;
      }
    });
    return cadena.current;
  }, [version]);

  const onCambio = useCallback((grafo, layout) => {
    setEdicion((e) => ({ ...e, grafo, layout }));
    pendiente.current = { grafo, layout };
    setGuardado("pendiente");
    clearTimeout(timer.current);
    timer.current = setTimeout(() => { guardarYa(); }, AUTOSAVE_MS);
  }, [guardarYa]);

  useEffect(() => () => clearTimeout(timer.current), []);

  // ── Acciones ──
  async function ejecutar(fn, { despues } = {}) {
    setError("");
    try {
      const r = await fn();
      setModal(null);
      await recargarProcesos();
      await (despues ? despues(r) : cargarProceso(procesoId));
    } catch (e) {
      const extra = problemasDeError(e);
      if (modal) setModal((m) => (m ? { ...m, error: mensajeDeError(e), problemas: extra } : m));
      else setError([mensajeDeError(e), ...extra].join(" · "));
    }
  }

  const nuevoBorrador = () => ejecutar(() => crearBorrador(procesoId), { despues: (v) => cargarProceso(procesoId, v.id) });

  async function pedirPublicar() {
    if (!(await guardarYa())) return;
    let diff = null;
    if (proceso.publicada) {
      try { diff = (await compararVersiones(proceso.publicada.id, version.id)).diff; } catch { /* el modal igual sirve */ }
    }
    let menos = false;
    if (proceso.publicada) {
      try { menos = cantidadAprobaciones(edicion.grafo) < cantidadAprobaciones((await verVersion(proceso.publicada.id)).grafo); } catch { /* opcional */ }
    }
    setModal({ tipo: "publicar", nota: version.nota || "", diff, menos });
  }

  async function compararCon(vid) {
    if (!vid) { setComparacion(null); return; }
    try {
      const anterior = proceso.versiones.find((x) => String(x.id) === String(vid));
      const { diff } = await compararVersiones(vid, version.id);
      setComparacion({ contra: anterior, diff });
    } catch (e) {
      setError(mensajeDeError(e, "No se pudo comparar"));
    }
  }

  const textoGuardado = { pendiente: "Cambios sin guardar…", guardando: "Guardando…", guardado: "Guardado",
    conflicto: "Otro usuario cambió este borrador: recargá", error: "No se pudo guardar" }[guardado] || "";

  if (cargando) return <Card>Cargando…</Card>;

  const porModulo = procesos.reduce((acc, p) => { (acc[p.modulo] ||= []).push(p); return acc; }, {});
  const errs = errores(problemas);

  return (
    <div className="grid grid-cols-1 xl:grid-cols-[240px_1fr] gap-4">
      <nav aria-label="Procesos" className="grid gap-4 content-start">
        {Object.entries(porModulo).map(([modulo, ps]) => (
          <div key={modulo}>
            <h2 className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-1">{MODULOS[modulo] || modulo}</h2>
            <ul className="grid gap-1">
              {ps.map((p) => (
                <li key={p.id}>
                  <button type="button" onClick={() => setProcesoId(p.id)} aria-current={p.id === procesoId ? "true" : undefined}
                          className={`w-full text-left px-3 py-2 rounded-lg border ${p.id === procesoId ? "border-blue-500 bg-blue-50" : "border-gray-200 bg-surface hover:bg-gray-50"}`}>
                    <span className="block text-sm font-medium text-gray-800">{p.nombre}</span>
                    <span className="flex flex-wrap gap-1 mt-1">
                      <Pill tono={p.habilitado ? "ok" : "neutral"}>{p.habilitado ? "Habilitado" : "Deshabilitado"}</Pill>
                      {p.publicada && <Pill tono="neutral">v{p.publicada.numero}</Pill>}
                      {p.borrador && <Pill tono="warn">Borrador</Pill>}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>

      <section className="grid gap-3 content-start min-w-0">
        {error && <Alerta>{error}</Alerta>}
        {!puede.editar && <Alerta tipo="warn">Sólo lectura: armar borradores requiere el permiso configuraciones:workflow:write.</Alerta>}

        {proceso && (
          <Card padding={false}>
            <div className="flex flex-wrap items-center gap-2 px-4 py-3">
              <div className="min-w-0">
                <h2 className="font-semibold text-gray-800">{proceso.nombre}</h2>
                <p className="text-sm text-gray-500">{proceso.descripcion}</p>
              </div>
              <span className="flex-1" />
              <Field label="Versión" className="!flex-row items-center !gap-2">
                <select className="input !py-1 !w-auto" aria-label="Versión" value={version?.id ?? ""}
                        onChange={async (e) => { if (await guardarYa()) abrirVersion(e.target.value); }}>
                  {(proceso.versiones || []).map((v) => (
                    <option key={v.id} value={v.id}>v{v.numero} · {v.estado.toLowerCase()}</option>
                  ))}
                </select>
              </Field>
              {version && <Pill tono={TONO_ESTADO[version.estado]}>{version.estado}</Pill>}
              {textoGuardado && <span role="status" className="text-xs text-gray-500">{textoGuardado}</span>}
            </div>
            <div className="flex flex-wrap items-center gap-2 px-4 py-2 border-t border-gray-200">
              {puede.editar && !proceso.borrador && <Boton variante="secundario" onClick={nuevoBorrador}>Nuevo borrador</Boton>}
              {puede.editar && esBorrador && (
                <Boton variante="secundario" onClick={() => setModal({ tipo: "descartar" })}>Descartar borrador</Boton>
              )}
              {puede.publicar && esBorrador && (
                <Boton onClick={pedirPublicar} disabled={errs.length > 0 || incompatibles.length > 0}
                       title={errs.length ? "Corregí los errores antes de publicar" : incompatibles.length ? "Usa nodos que el motor actual todavía no ejecuta" : undefined}>
                  Publicar…
                </Boton>
              )}
              {puede.publicar && version?.estado === "PUBLICADA" && (
                <Boton variante="danger" onClick={() => setModal({ tipo: "retirar" })}>Retirar</Boton>
              )}
              {puede.publicar && (
                <Boton variante="secundario" onClick={() => setModal({ tipo: "habilitar", valor: !proceso.habilitado })}>
                  {proceso.habilitado ? "Deshabilitar" : "Habilitar"}
                </Boton>
              )}
              <span className="flex-1" />
              <label className="text-sm text-gray-600 flex items-center gap-1">
                <GitCompare size={14} aria-hidden /> Comparar con
                <select className="input !py-1 !w-auto" aria-label="Comparar con" value={comparacion?.contra?.id ?? ""}
                        onChange={(e) => compararCon(e.target.value)}>
                  <option value="">—</option>
                  {(proceso.versiones || []).filter((v) => v.id !== version?.id).map((v) => (
                    <option key={v.id} value={v.id}>v{v.numero}</option>
                  ))}
                </select>
              </label>
            </div>
            {version && (
              <p className="px-4 pb-2 text-xs text-gray-500">
                {version.publicadaPor ? `Publicada por ${version.publicadaPor} el ${fecha(version.publicadaEn)}. ` : ""}
                {version.modificadaPor ? `Último cambio de ${version.modificadaPor}. ` : ""}
                {version.nota}
              </p>
            )}
          </Card>
        )}

        {esBorrador && incompatibles.length > 0 && (
          <Alerta tipo="warn">
            Este borrador se puede guardar y validar, pero todavía no publicar: Créditos y Tesorería ejecutan sólo aprobaciones en serie por rol (el motor nuevo llega en la fase 3).
            <ul className="list-disc ml-5 mt-1">{incompatibles.map((m) => <li key={m}>{m}</li>)}</ul>
          </Alerta>
        )}

        {comparacion && (
          <Card>
            <h3 className="text-sm font-semibold text-gray-700 mb-1">
              Cambios de v{comparacion.contra?.numero} a v{version?.numero}
            </h3>
            {comparacion.diff.iguales ? <p className="text-sm text-gray-500">Son iguales.</p> : (
              <ul className="text-sm grid gap-0.5">{comparacion.diff.resumen.map((l) => <li key={l}>{l}</li>)}</ul>
            )}
            <p className="text-xs text-gray-500 mt-1">En el diagrama: verde = agregado, ámbar = modificado.</p>
          </Card>
        )}

        {edicion && (
          <EditorWorkflow proceso={proceso} version={version} grafo={edicion.grafo} layout={edicion.layout}
                          problemas={problemas} variables={variables} personas={personas} soloLectura={soloLectura}
                          marcas={comparacion ? marcasDiff(comparacion.diff) : {}} onCambio={onCambio} onError={setError} />
        )}
      </section>

      {modal?.tipo === "publicar" && (
        <Modal titulo={`Publicar la versión ${version.numero}`} eyebrow={proceso.nombre} onClose={() => setModal(null)} ancho="max-w-lg"
               footer={<>
                 <span className="flex-1" />
                 <Boton variante="secundario" onClick={() => setModal(null)}>Cancelar</Boton>
                 <Boton onClick={() => ejecutar(() => publicarVersion(version.id, modal.nota))}>Publicar</Boton>
               </>}>
          <div className="grid gap-3">
            {modal.error && <Alerta>{[modal.error, ...(modal.problemas || [])].join(" · ")}</Alerta>}
            <p className="text-sm text-gray-600">
              Desde que se publica, las operaciones nuevas se aprueban con esta versión. Te vamos a pedir el código del doble factor.
            </p>
            {modal.diff && (
              <div>
                <p className="text-sm font-medium text-gray-700">Cambios respecto de la versión vigente</p>
                <ul className="text-sm text-gray-600 list-disc ml-5">{modal.diff.resumen.map((l) => <li key={l}>{l}</li>)}</ul>
              </div>
            )}
            {modal.menos && (
              <Alerta tipo="warn">
                Esta versión tiene menos aprobaciones que la vigente. Hasta que llegue el motor nuevo, Créditos y Tesorería aplican el cambio también a las operaciones que ya están esperando aprobación.
              </Alerta>
            )}
            <Field label="Qué cambia y por qué (queda en el historial)">
              <textarea className="input" rows={2} maxLength={300} value={modal.nota}
                        onChange={(e) => setModal((m) => ({ ...m, nota: e.target.value }))} />
            </Field>
          </div>
        </Modal>
      )}

      {modal?.tipo === "retirar" && (
        <Confirmacion titulo="Retirar la versión publicada" confirmar="Retirar"
                      mensaje={`${proceso.nombre} · v${version.numero}\nEl proceso queda sin workflow vigente y se DESHABILITA: deja de exigirse la aprobación hasta que publiques otra versión.`}
                      onConfirmar={() => ejecutar(() => retirarVersion(version.id))} onCancelar={() => setModal(null)} />
      )}
      {modal?.tipo === "descartar" && (
        <Confirmacion titulo="Descartar el borrador" confirmar="Descartar"
                      mensaje={`v${version.numero}\nSe pierden los cambios del borrador. La versión publicada no cambia.`}
                      onConfirmar={() => { clearTimeout(timer.current); pendiente.current = null; ejecutar(() => descartarBorrador(version.id)); }}
                      onCancelar={() => setModal(null)} />
      )}
      {modal?.tipo === "habilitar" && (
        <Confirmacion titulo={modal.valor ? "Habilitar el workflow" : "Deshabilitar el workflow"}
                      confirmar={modal.valor ? "Habilitar" : "Deshabilitar"} danger={!modal.valor}
                      mensaje={modal.valor
                        ? `${proceso.nombre}\nDesde ahora la operación queda pendiente hasta completar la aprobación de la versión publicada.`
                        : `${proceso.nombre}\nDeja de exigirse la aprobación: la operación se ejecuta con el permiso de aprobar de la pantalla, sin cuatro-ojos.`}
                      onConfirmar={() => ejecutar(() => habilitarProceso(proceso.id, modal.valor))} onCancelar={() => setModal(null)} />
      )}
    </div>
  );
}
