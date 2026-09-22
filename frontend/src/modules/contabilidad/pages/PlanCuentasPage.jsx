import { useEffect, useState } from "react";
import {
  cerrarEjercicio, crearCuenta, crearEjercicio, editarCuenta, listarCuentas, listarEjercicios,
  mensajeDeError,
} from "../../../api/contabilidad";
import { PermissionGate } from "../../../components/PrivateRoute";
import { Alerta, Boton, Card, Field, Modal, PageHeader, Toolbar } from "../../../components/ui";
import { Confirmacion } from "../../../components/ui/Confirmacion";
import { DataTable } from "../../../components/ui/DataTable";
import { Pill } from "../../../components/ui/Pill";
import { fecha } from "../formato";

const VACIA = { codigo: "", nombre: "", rubro: "ACTIVO", imputable: true, saldo_normal: "DEUDOR",
                moneda: "ARS", ajustable: false, requiere_centro: false, descripcion: "", activa: true };

export default function PlanCuentasPage() {
  const [cuentas, setCuentas] = useState([]);
  const [rubros, setRubros] = useState([]);
  const [ejercicios, setEjercicios] = useState([]);
  const [filtro, setFiltro] = useState("");
  const [form, setForm] = useState(null);
  const [nuevoEjercicio, setNuevoEjercicio] = useState(null);
  const [cerrando, setCerrando] = useState(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [cargando, setCargando] = useState(true);

  const cargar = () => {
    setCargando(true);
    Promise.all([listarCuentas(), listarEjercicios()])
      .then(([c, e]) => { setCuentas(c.items); setRubros(c.rubros); setEjercicios(e.items); })
      .catch((e) => setError(mensajeDeError(e)))
      .finally(() => setCargando(false));
  };
  useEffect(cargar, []);

  const guardar = async () => {
    setError("");
    try {
      form.id ? await editarCuenta(form.id, form) : await crearCuenta(form);
      setForm(null); setOk("Plan de cuentas actualizado."); cargar();
    } catch (e) { setError(mensajeDeError(e)); }
  };

  const abrirEjercicio = async () => {
    setError("");
    try {
      await crearEjercicio(nuevoEjercicio);
      setNuevoEjercicio(null); setOk("Ejercicio abierto."); cargar();
    } catch (e) { setError(mensajeDeError(e)); }
  };

  const confirmarCierre = async () => {
    setError("");
    try {
      const r = await cerrarEjercicio(cerrando.id);
      setCerrando(null);
      setOk(`Ejercicio ${r.ejercicio} cerrado. Resultado refundido: ${r.resultado}.`);
      cargar();
    } catch (e) { setError(mensajeDeError(e)); setCerrando(null); }
  };

  const filtradas = cuentas.filter((c) => !filtro ||
    `${c.codigo} ${c.nombre} ${c.rubro}`.toLowerCase().includes(filtro.toLowerCase()));

  return (
    <div className="space-y-4">
      <PageHeader titulo="Plan de cuentas y ejercicios"
                  descripcion="Las cuentas donde imputan los asientos y los ejercicios contables. Una cuenta de agrupación no recibe asientos.">
        <PermissionGate moduleCode="contabilidad" action="definiciones:write">
          <Boton onClick={() => setForm({ ...VACIA })}>＋ Nueva cuenta</Boton>
        </PermissionGate>
      </PageHeader>

      <Alerta>{error}</Alerta>
      {ok && <Alerta tipo="ok">{ok}</Alerta>}

      <Card>
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="text-sm font-semibold text-gray-700 mr-auto">Ejercicios</h2>
          <PermissionGate moduleCode="contabilidad" action="ejercicios:write">
            <Boton variante="secundario" onClick={() => {
              const anio = new Date().getFullYear() + 1;
              setNuevoEjercicio({ numero: anio, desde: `${anio}-01-01`, hasta: `${anio}-12-31`, cuenta_resultado: "3.1.03" });
            }}>Abrir ejercicio</Boton>
          </PermissionGate>
        </div>
        <ul className="divide-y divide-gray-100 mt-2">
          {ejercicios.map((e) => (
            <li key={e.id} className="flex flex-wrap items-center gap-3 py-2 text-sm">
              <span className="font-medium text-gray-800">{e.numero}</span>
              <span className="text-gray-500">{fecha(e.desde)} – {fecha(e.hasta)}</span>
              <Pill tono={e.estado === "ABIERTO" ? "ok" : "neutral"}>{e.estado.toLowerCase()}</Pill>
              {e.cerradoPor && <span className="text-xs text-gray-400">cerrado por {e.cerradoPor}</span>}
              <span className="flex-1" />
              {e.estado === "ABIERTO" && (
                <PermissionGate moduleCode="contabilidad" action="ejercicios:write">
                  <Boton variante="danger" className="!px-3 !py-1.5 text-xs" onClick={() => setCerrando(e)}>Cerrar ejercicio</Boton>
                </PermissionGate>
              )}
            </li>
          ))}
        </ul>
      </Card>

      <Card padding={false}>
        <Toolbar>
          <Field label="Buscar">
            <input className="input w-64" placeholder="Código, nombre o rubro" value={filtro} onChange={(e) => setFiltro(e.target.value)} />
          </Field>
          <span className="ml-auto text-sm text-gray-500">{filtradas.length} de {cuentas.length} cuentas</span>
        </Toolbar>
        {cargando ? <p className="px-4 py-8 text-center text-sm text-gray-400">Cargando…</p> : (
          <div className="p-4">
            <DataTable rowKey={(c) => c.id} rows={filtradas} pageSize={50} clientSort defaultSort="codigo"
                       onRowClick={(c) => setForm({ ...c, saldo_normal: c.saldoNormal, requiere_centro: c.requiereCentro })}
              columns={[
                { key: "codigo", label: "Código", sortable: true },
                { key: "nombre", label: "Nombre", sortable: true, render: (c) => (
                  <span className={c.imputable ? "" : "font-semibold text-gray-800"}>{c.nombre}</span>) },
                { key: "rubro", label: "Rubro", sortable: true },
                { key: "tipo", label: "Tipo", render: (c) => (
                  <div className="flex flex-wrap gap-1">
                    <Pill tono={c.imputable ? "brand" : "neutral"}>{c.imputable ? "imputable" : "agrupación"}</Pill>
                    {c.ajustable && <Pill>ajustable</Pill>}
                    {!c.activa && <Pill tono="crit">de baja</Pill>}
                  </div>) },
                { key: "saldoNormal", label: "Saldo normal", render: (c) => c.saldoNormal.toLowerCase() },
              ]} emptyText="Sin cuentas" />
          </div>
        )}
      </Card>

      {form && (
        <Modal titulo={form.id ? `Cuenta ${form.codigo}` : "Nueva cuenta"} onClose={() => setForm(null)} ancho="max-w-2xl"
               footer={<>
                 <span className="flex-1" />
                 <Boton variante="secundario" onClick={() => setForm(null)}>Cancelar</Boton>
                 <PermissionGate moduleCode="contabilidad" action="definiciones:write">
                   <Boton disabled={!form.codigo.trim() || !form.nombre.trim()} onClick={guardar}>Guardar</Boton>
                 </PermissionGate>
               </>}>
          <div className="grid sm:grid-cols-2 gap-3">
            <Field label="Código"><input className="input w-full" value={form.codigo} onChange={(e) => setForm({ ...form, codigo: e.target.value })} /></Field>
            <Field label="Nombre"><input className="input w-full" value={form.nombre} onChange={(e) => setForm({ ...form, nombre: e.target.value })} /></Field>
            <Field label="Rubro">
              <select className="input w-full" value={form.rubro} onChange={(e) => setForm({ ...form, rubro: e.target.value })}>
                {rubros.map((r) => <option key={r} value={r}>{r}</option>)}
              </select>
            </Field>
            <Field label="Saldo normal">
              <select className="input w-full" value={form.saldo_normal} onChange={(e) => setForm({ ...form, saldo_normal: e.target.value })}>
                <option value="DEUDOR">Deudor</option><option value="ACREEDOR">Acreedor</option>
              </select>
            </Field>
          </div>
          <div className="flex flex-wrap gap-4 mt-3 text-sm text-gray-600">
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={form.imputable} onChange={(e) => setForm({ ...form, imputable: e.target.checked })} />
              Imputable (recibe asientos)
            </label>
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={form.ajustable} onChange={(e) => setForm({ ...form, ajustable: e.target.checked })} />
              Se ajusta por inflación
            </label>
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={form.requiere_centro} onChange={(e) => setForm({ ...form, requiere_centro: e.target.checked })} />
              Exige centro de costo
            </label>
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={form.activa} onChange={(e) => setForm({ ...form, activa: e.target.checked })} />
              Activa
            </label>
          </div>
        </Modal>
      )}

      {nuevoEjercicio && (
        <Modal titulo="Abrir ejercicio" onClose={() => setNuevoEjercicio(null)} ancho="max-w-md"
               footer={<>
                 <span className="flex-1" />
                 <Boton variante="secundario" onClick={() => setNuevoEjercicio(null)}>Cancelar</Boton>
                 <Boton onClick={abrirEjercicio}>Abrir</Boton>
               </>}>
          <div className="space-y-3">
            <Field label="Ejercicio"><input type="number" className="input w-full" value={nuevoEjercicio.numero}
                   onChange={(e) => setNuevoEjercicio({ ...nuevoEjercicio, numero: Number(e.target.value) })} /></Field>
            <Field label="Desde"><input type="date" className="input w-full" value={nuevoEjercicio.desde}
                   onChange={(e) => setNuevoEjercicio({ ...nuevoEjercicio, desde: e.target.value })} /></Field>
            <Field label="Hasta"><input type="date" className="input w-full" value={nuevoEjercicio.hasta}
                   onChange={(e) => setNuevoEjercicio({ ...nuevoEjercicio, hasta: e.target.value })} /></Field>
          </div>
        </Modal>
      )}

      {cerrando && (
        <Confirmacion titulo={`Cerrar el ejercicio ${cerrando.numero}`} confirmar="Cerrar ejercicio"
                      mensaje={"Se refunden los resultados contra la cuenta de resultado del ejercicio y no se podrán registrar más asientos en ese período.\nNo se puede cerrar si quedan transacciones sin contabilizar."}
                      onConfirmar={confirmarCierre} onCancelar={() => setCerrando(null)} />
      )}
    </div>
  );
}
