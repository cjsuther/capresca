import { useEffect, useState } from "react";
import { listarEventos, mensajeDeError, resumenAuditoria, verEvento } from "../../../api/auditoria";
import { Alerta, Boton, Card, Field, Kpis, LimpiarFiltros, Modal, PageHeader, Toolbar } from "../../../components/ui";
import { DataTable } from "../../../components/ui/DataTable";
import { Pill } from "../../../components/ui/Pill";

const OPERACIONES = {
  ALTA: ["Alta", "ok"], MODIFICACION: ["Modificación", "brand"], BAJA: ["Baja", "crit"],
  ACCION: ["Acción", "neutral"], ACCESO: ["Acceso", "warn"],
};
const VACIOS = { usuario: "", modulo: "", operacion: "", texto: "", desde: "", hasta: "", solo_errores: false };

const fechaHora = (v) => {
  if (!v) return "—";
  const d = new Date(v);
  return isNaN(d) ? String(v) : d.toLocaleString("es-AR", { dateStyle: "short", timeStyle: "medium" });
};

const valor = (v) => (v === null || v === undefined || v === "" ? "—" : String(v));

/** Qué cambió: {campo: [antes, después]} o {campo: valor} en las altas. */
function Cambios({ cambios }) {
  const filas = Object.entries(cambios || {});
  if (!filas.length) return <p className="text-sm text-gray-500">Sin detalle de campos.</p>;
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b border-gray-200 bg-gray-50 text-left text-xs text-gray-500">
          <th className="px-3 py-2 font-medium">Campo</th>
          <th className="px-3 py-2 font-medium">Antes</th>
          <th className="px-3 py-2 font-medium">Después</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-gray-100">
        {filas.map(([campo, v]) => {
          const [antes, despues] = Array.isArray(v) ? v : [null, v];
          return (
            <tr key={campo}>
              <td className="px-3 py-1.5 font-medium text-gray-700">{campo}</td>
              <td className="px-3 py-1.5 text-gray-500 line-through break-all">{valor(antes)}</td>
              <td className="px-3 py-1.5 text-gray-800 break-all">{valor(despues)}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

export default function EventosPage() {
  const [datos, setDatos] = useState({ items: [], total: 0 });
  const [resumen, setResumen] = useState(null);
  const [filtros, setFiltros] = useState(VACIOS);
  const [offset, setOffset] = useState(0);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [detalle, setDetalle] = useState(null);
  const limit = 50;

  useEffect(() => { resumenAuditoria().then(setResumen).catch(() => {}); }, []);

  useEffect(() => {
    setCargando(true);
    setError("");
    const params = Object.fromEntries(Object.entries(filtros).filter(([, v]) => v !== "" && v !== false));
    listarEventos({ ...params, limit, offset })
      .then(setDatos)
      .catch((e) => setError(mensajeDeError(e)))
      .finally(() => setCargando(false));
  }, [filtros, offset]);

  const cambiar = (campo, v) => { setOffset(0); setFiltros((f) => ({ ...f, [campo]: v })); };
  const hayFiltros = JSON.stringify(filtros) !== JSON.stringify(VACIOS);

  const abrir = (e) => verEvento(e.id).then(setDetalle).catch((err) => setError(mensajeDeError(err)));

  const columnas = [
    { key: "fecha", label: "Cuándo", render: (e) => <span className="whitespace-nowrap tabular-nums">{fechaHora(e.fecha)}</span> },
    { key: "usuario", label: "Quién", render: (e) => (
      <div><p className="font-medium text-gray-800">{e.usuario || "—"}</p>
        <p className="text-xs text-gray-400">{e.ip}</p></div>
    ) },
    { key: "modulo", label: "Módulo", render: (e) => e.modulo || "—" },
    { key: "operacion", label: "Qué hizo", render: (e) => {
      const [txt, tono] = OPERACIONES[e.operacion] || [e.operacion, "neutral"];
      return (
        <div className="flex flex-wrap items-center gap-1">
          <Pill tono={tono}>{txt}</Pill>
          {e.exito === false && <Pill tono="crit">falló</Pill>}
        </div>
      );
    } },
    { key: "entidad", label: "Sobre qué", render: (e) => (
      e.entidad
        ? <div><p className="text-gray-800">{e.entidad}</p><p className="text-xs text-gray-400">{e.entidadId}</p></div>
        : <span className="text-xs text-gray-400">{e.metodo} {e.ruta}</span>
    ) },
    { key: "descripcion", label: "Detalle", render: (e) => (
      <span className="text-gray-600">{e.descripcion || "—"}</span>
    ) },
  ];

  return (
    <div className="space-y-4">
      <PageHeader titulo="Registro de actividad"
                  descripcion="Qué hizo cada usuario con la información del sistema: qué registros agregó, modificó o eliminó, en qué módulo y desde dónde." />

      <Alerta>{error}</Alerta>

      {resumen && (
        <Kpis items={[
          { label: "Eventos registrados", valor: resumen.total.toLocaleString("es-AR") },
          { label: "Último", valor: fechaHora(resumen.ultimo) },
          { label: "Módulos con actividad", valor: resumen.modulos.length },
          { label: "Se conserva", valor: `${Math.round(resumen.retencionDias / 365)} años` },
        ]} />
      )}

      <Card padding={false}>
        <Toolbar>
          <Field label="Usuario">
            <input className="input w-40" value={filtros.usuario} onChange={(e) => cambiar("usuario", e.target.value)} placeholder="Todos" />
          </Field>
          <Field label="Módulo">
            <select className="input" value={filtros.modulo} onChange={(e) => cambiar("modulo", e.target.value)}>
              <option value="">Todos</option>
              {(resumen?.modulos || []).map((m) => <option key={m.valor} value={m.valor}>{m.valor}</option>)}
            </select>
          </Field>
          <Field label="Qué hizo">
            <select className="input" value={filtros.operacion} onChange={(e) => cambiar("operacion", e.target.value)}>
              <option value="">Todo</option>
              {Object.entries(OPERACIONES).map(([v, [t]]) => <option key={v} value={v}>{t}</option>)}
            </select>
          </Field>
          <Field label="Desde">
            <input type="date" className="input" value={filtros.desde} onChange={(e) => cambiar("desde", e.target.value)} />
          </Field>
          <Field label="Hasta">
            <input type="date" className="input" value={filtros.hasta} onChange={(e) => cambiar("hasta", e.target.value)} />
          </Field>
          <Field label="Buscar">
            <input className="input w-48" value={filtros.texto} onChange={(e) => cambiar("texto", e.target.value)}
                   placeholder="Registro, ruta, texto" />
          </Field>
          <label className="flex items-center gap-2 text-sm text-gray-600">
            <input type="checkbox" checked={filtros.solo_errores} onChange={(e) => cambiar("solo_errores", e.target.checked)} />
            Sólo lo que falló
          </label>
          <LimpiarFiltros activo={hayFiltros} onClear={() => { setOffset(0); setFiltros(VACIOS); }} />
        </Toolbar>
        {cargando
          ? <p className="px-4 py-8 text-center text-gray-400 text-sm">Cargando…</p>
          : <div className="p-4">
              <DataTable columns={columnas} rows={datos.items} rowKey={(e) => e.id} onRowClick={abrir}
                         total={datos.total} limit={limit} offset={offset} onPage={setOffset}
                         emptyText="No hay actividad con estos filtros" />
            </div>}
      </Card>

      {detalle && (
        <Modal titulo={`${detalle.entidad || detalle.modulo} ${detalle.entidadId || ""}`.trim()}
               eyebrow={`${OPERACIONES[detalle.operacion]?.[0] || detalle.operacion} · ${fechaHora(detalle.fecha)}`}
               onClose={() => setDetalle(null)}
               footer={<><span className="flex-1" /><Boton variante="secundario" onClick={() => setDetalle(null)}>Cerrar</Boton></>}>
          <dl className="grid sm:grid-cols-3 gap-3 text-sm mb-4">
            <div><dt className="text-xs text-gray-500">Usuario</dt><dd className="font-medium">{detalle.usuario || "—"}</dd></div>
            <div><dt className="text-xs text-gray-500">Módulo</dt><dd className="font-medium">{detalle.modulo || "—"}</dd></div>
            <div><dt className="text-xs text-gray-500">Desde</dt><dd className="font-medium">{detalle.ip || "—"}</dd></div>
            <div className="sm:col-span-2"><dt className="text-xs text-gray-500">Operación</dt>
              <dd className="font-medium break-all">{detalle.metodo} {detalle.ruta || detalle.descripcion}</dd></div>
            <div><dt className="text-xs text-gray-500">Resultado</dt>
              <dd className="font-medium">{detalle.exito === false ? `Falló (${detalle.estadoHttp || "—"})` : "OK"}</dd></div>
          </dl>
          {detalle.detalle && <p className="text-sm text-gray-600 mb-3">{detalle.detalle}</p>}
          <h3 className="text-sm font-semibold text-gray-700 mb-1">Qué cambió</h3>
          <Cambios cambios={detalle.cambios} />
          {!!detalle.relacionados?.length && (
            <>
              <h3 className="text-sm font-semibold text-gray-700 mt-4 mb-1">Misma operación</h3>
              <ul className="space-y-1">
                {detalle.relacionados.map((r) => (
                  <li key={r.id} className="text-sm text-gray-600">
                    <span className="text-xs text-gray-400 mr-2">{r.origen === "GATEWAY" ? "Pedido" : "Detalle"}</span>
                    {r.entidad ? `${r.entidad} ${r.entidadId}` : `${r.metodo} ${r.ruta}`}
                    {r.descripcion ? ` · ${r.descripcion}` : ""}
                  </li>
                ))}
              </ul>
            </>
          )}
        </Modal>
      )}
    </div>
  );
}
