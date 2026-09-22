import { useEffect, useState } from "react";
import {
  aperturaEjercicio, cerrarEjercicio, crearEjercicio, crearEmpresa, editarEmpresa, listarEjercicios,
  listarEmpresas, mensajeDeError, reabrirEjercicio,
} from "../../../api/contabilidad";
import { PermissionGate } from "../../../components/PrivateRoute";
import { Alerta, Boton, Card, Field, Modal, PageHeader } from "../../../components/ui";
import { Confirmacion } from "../../../components/ui/Confirmacion";
import { Pill } from "../../../components/ui/Pill";
import { fecha } from "../formato";

const CONDICIONES = ["RESPONSABLE_INSCRIPTO", "MONOTRIBUTO", "EXENTO", "NO_ALCANZADO"];

/** Ejercicios contables (apertura, cierre y reapertura) y datos del ente (CUIT, condición ante el IVA). */
export default function EjerciciosPage() {
  const [ejercicios, setEjercicios] = useState([]);
  const [empresas, setEmpresas] = useState([]);
  const [nuevo, setNuevo] = useState(null);
  const [empresa, setEmpresa] = useState(null);
  const [confirmando, setConfirmando] = useState(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");

  const cargar = () => Promise.all([listarEjercicios(), listarEmpresas()])
    .then(([e, m]) => { setEjercicios(e.items); setEmpresas(m.items); })
    .catch((e) => setError(mensajeDeError(e)));
  useEffect(() => { cargar(); }, []);

  const correr = async (fn, exito) => {
    setError(""); setOk("");
    try { const r = await fn(); setOk(typeof exito === "function" ? exito(r) : exito); setConfirmando(null); cargar(); }
    catch (e) { setError(mensajeDeError(e)); setConfirmando(null); }
  };

  const guardarEmpresa = () => correr(
    () => (empresa.id ? editarEmpresa(empresa.id, empresa) : crearEmpresa(empresa)),
    () => { setEmpresa(null); return "Ente contable guardado."; });

  return (
    <div className="space-y-4">
      <PageHeader titulo="Ejercicios y ente contable"
                  descripcion="Los períodos contables (apertura, cierre y reapertura) y los datos fiscales del ente.">
        <PermissionGate moduleCode="contabilidad" action="ejercicios:write">
          <Boton onClick={() => {
            const anio = (ejercicios[0]?.numero || new Date().getFullYear()) + 1;
            setNuevo({ numero: anio, desde: `${anio}-01-01`, hasta: `${anio}-12-31`, cuenta_resultado: "3.3" });
          }}>＋ Abrir ejercicio</Boton>
        </PermissionGate>
      </PageHeader>

      <Alerta>{error}</Alerta>
      {ok && <Alerta tipo="ok">{ok}</Alerta>}

      <Card padding={false}>
        <h2 className="px-4 py-3 text-sm font-semibold text-gray-700 border-b border-gray-200">Ejercicios</h2>
        <ul className="divide-y divide-gray-100">
          {ejercicios.map((e) => (
            <li key={e.id} className="flex flex-wrap items-center gap-3 px-4 py-3 text-sm">
              <span className="font-medium text-gray-800">{e.numero}</span>
              <span className="text-gray-500">{fecha(e.desde)} – {fecha(e.hasta)}</span>
              <Pill tono={e.estado === "ABIERTO" ? "ok" : "neutral"}>{e.estado.toLowerCase()}</Pill>
              <span className="text-xs text-gray-400">resultado → {e.cuentaResultado}</span>
              {e.cerradoPor && <span className="text-xs text-gray-400">cerrado por {e.cerradoPor}</span>}
              <span className="flex-1" />
              <PermissionGate moduleCode="contabilidad" action="ejercicios:write">
                {e.estado === "ABIERTO" ? (
                  <>
                    <Boton variante="secundario" className="!px-3 !py-1.5 text-xs"
                           onClick={() => correr(() => aperturaEjercicio(e.id),
                                                 (r) => `Asiento de apertura N° ${r.numero} registrado.`)}>
                      Asiento de apertura
                    </Boton>
                    <Boton variante="danger" className="!px-3 !py-1.5 text-xs" onClick={() => setConfirmando({
                      titulo: `Cerrar el ejercicio ${e.numero}`, confirmar: "Cerrar ejercicio",
                      mensaje: "Se refunden los resultados contra la cuenta de resultado y no se podrán registrar más asientos en ese período.\nNo se puede cerrar si quedan transacciones sin contabilizar.",
                      onSi: () => correr(() => cerrarEjercicio(e.id),
                                         (r) => `Ejercicio ${r.ejercicio} cerrado. Resultado refundido: ${r.resultado}.`),
                    })}>Cerrar</Boton>
                  </>
                ) : (
                  <Boton variante="secundario" className="!px-3 !py-1.5 text-xs" onClick={() => setConfirmando({
                    titulo: `Reabrir el ejercicio ${e.numero}`, confirmar: "Reabrir", danger: false,
                    mensaje: "Se anula su asiento de cierre (los dos quedan en el libro) y el período vuelve a admitir asientos.",
                    onSi: () => correr(() => reabrirEjercicio(e.id), "Ejercicio reabierto."),
                  })}>Reabrir</Boton>
                )}
              </PermissionGate>
            </li>
          ))}
          {!ejercicios.length && <li className="px-4 py-6 text-center text-sm text-gray-400">Sin ejercicios</li>}
        </ul>
      </Card>

      <Card padding={false}>
        <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-200">
          <h2 className="text-sm font-semibold text-gray-700 mr-auto">Ente contable</h2>
          <PermissionGate moduleCode="contabilidad" action="definiciones:write">
            <Boton variante="secundario" className="!px-3 !py-1.5 text-xs"
                   onClick={() => setEmpresa({ razon_social: "", cuit: "", condicion_iva: CONDICIONES[0],
                                               domicilio: "" })}>＋ Nuevo ente</Boton>
          </PermissionGate>
        </div>
        <ul className="divide-y divide-gray-100">
          {empresas.map((e) => (
            <li key={e.id} className="flex flex-wrap items-center gap-3 px-4 py-3 text-sm">
              <span className="font-medium text-gray-800">{e.razonSocial}</span>
              <span className="text-gray-500 tabular-nums">{e.cuit || "sin CUIT"}</span>
              <span className="text-xs text-gray-400">{e.condicionIva.replaceAll("_", " ").toLowerCase()}</span>
              {e.predeterminada && <Pill tono="brand">predeterminado</Pill>}
              <span className="flex-1" />
              <PermissionGate moduleCode="contabilidad" action="definiciones:write">
                <button className="text-xs text-blue-600 hover:underline"
                        onClick={() => setEmpresa({ id: e.id, razon_social: e.razonSocial, cuit: e.cuit,
                                                    condicion_iva: e.condicionIva, domicilio: e.domicilio })}>
                  Editar
                </button>
              </PermissionGate>
            </li>
          ))}
        </ul>
      </Card>

      {nuevo && (
        <Modal titulo="Abrir ejercicio" onClose={() => setNuevo(null)} ancho="max-w-md"
               footer={<>
                 <span className="flex-1" />
                 <Boton variante="secundario" onClick={() => setNuevo(null)}>Cancelar</Boton>
                 <Boton onClick={() => correr(() => crearEjercicio(nuevo), () => { setNuevo(null); return "Ejercicio abierto."; })}>
                   Abrir
                 </Boton>
               </>}>
          <div className="space-y-3">
            <Field label="Ejercicio">
              <input type="number" className="input w-full" value={nuevo.numero}
                     onChange={(e) => setNuevo({ ...nuevo, numero: Number(e.target.value) })} />
            </Field>
            <Field label="Desde">
              <input type="date" className="input w-full" value={nuevo.desde}
                     onChange={(e) => setNuevo({ ...nuevo, desde: e.target.value })} />
            </Field>
            <Field label="Hasta">
              <input type="date" className="input w-full" value={nuevo.hasta}
                     onChange={(e) => setNuevo({ ...nuevo, hasta: e.target.value })} />
            </Field>
            <Field label="Cuenta de resultado del ejercicio">
              <input className="input w-full" value={nuevo.cuenta_resultado}
                     onChange={(e) => setNuevo({ ...nuevo, cuenta_resultado: e.target.value })} />
            </Field>
          </div>
        </Modal>
      )}

      {empresa && (
        <Modal titulo={empresa.id ? "Ente contable" : "Nuevo ente contable"} onClose={() => setEmpresa(null)}
               ancho="max-w-lg"
               footer={<>
                 <span className="flex-1" />
                 <Boton variante="secundario" onClick={() => setEmpresa(null)}>Cancelar</Boton>
                 <Boton disabled={!empresa.razon_social.trim()} onClick={guardarEmpresa}>Guardar</Boton>
               </>}>
          <div className="grid sm:grid-cols-2 gap-3">
            <Field label="Razón social" className="sm:col-span-2">
              <input className="input w-full" value={empresa.razon_social}
                     onChange={(e) => setEmpresa({ ...empresa, razon_social: e.target.value })} />
            </Field>
            <Field label="CUIT">
              <input className="input w-full" value={empresa.cuit}
                     onChange={(e) => setEmpresa({ ...empresa, cuit: e.target.value })} />
            </Field>
            <Field label="Condición frente al IVA">
              <select className="input w-full" value={empresa.condicion_iva}
                      onChange={(e) => setEmpresa({ ...empresa, condicion_iva: e.target.value })}>
                {CONDICIONES.map((c) => <option key={c} value={c}>{c.replaceAll("_", " ").toLowerCase()}</option>)}
              </select>
            </Field>
            <Field label="Domicilio" className="sm:col-span-2">
              <input className="input w-full" value={empresa.domicilio}
                     onChange={(e) => setEmpresa({ ...empresa, domicilio: e.target.value })} />
            </Field>
          </div>
        </Modal>
      )}

      {confirmando && (
        <Confirmacion titulo={confirmando.titulo} mensaje={confirmando.mensaje}
                      confirmar={confirmando.confirmar} danger={confirmando.danger !== false}
                      onConfirmar={confirmando.onSi} onCancelar={() => setConfirmando(null)} />
      )}
    </div>
  );
}
