import { useEffect, useState } from "react";
import { listarTransacciones, mensajeDeError, reprocesar, sinDefinir, verTransaccion } from "../../../api/contabilidad";
import { PermissionGate } from "../../../components/PrivateRoute";
import { useHasPermission } from "../../../context/usePermissions";
import { Alerta, Boton, Card, Field, Kpis, Modal, PageHeader, Toolbar } from "../../../components/ui";
import { DataTable } from "../../../components/ui/DataTable";
import { Pill } from "../../../components/ui/Pill";
import { FormularioDefinicion } from "../components/FormularioDefinicion";
import { ESTADO_TRANSACCION, fecha, money } from "../formato";

export default function TransaccionesPage() {
  const puedeDefinir = useHasPermission("contabilidad", "definiciones:write");
  const [pendientes, setPendientes] = useState([]);
  const [datos, setDatos] = useState({ items: [], total: 0, pendientes: 0, errores: 0 });
  const [estado, setEstado] = useState("PENDIENTE_CONFIGURACION,ERROR");
  const [definiendo, setDefiniendo] = useState(null);
  const [detalle, setDetalle] = useState(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [cargando, setCargando] = useState(true);

  const cargar = () => {
    setCargando(true);
    Promise.all([sinDefinir(), listarTransacciones({ estado, limit: 100 })])
      .then(([p, t]) => { setPendientes(p.items); setDatos(t); })
      .catch((e) => setError(mensajeDeError(e)))
      .finally(() => setCargando(false));
  };
  useEffect(cargar, [estado]);   // eslint-disable-line react-hooks/exhaustive-deps

  const volverAProcesar = async () => {
    setError(""); setOk("");
    try {
      const r = await reprocesar();
      setOk(`Se contabilizaron ${r.contabilizadas}; quedan ${r.pendientes} sin definición y ${r.errores} con error.`);
      cargar();
    } catch (e) { setError(mensajeDeError(e)); }
  };

  const columnas = [
    { key: "fecha", label: "Fecha", render: (t) => fecha(t.fecha) },
    { key: "modulo", label: "Módulo" },
    { key: "tipo", label: "Transacción" },
    { key: "referencia", label: "Referencia", render: (t) => <span className="font-medium text-gray-800">{t.referencia}</span> },
    { key: "importe", label: "Datos", render: (t) => (
      <span className="text-xs text-gray-500">
        {Object.entries(t.datos).filter(([, v]) => typeof v === "number").slice(0, 3)
          .map(([k, v]) => `${k}: ${money(v)}`).join(" · ") || "—"}
      </span>
    ) },
    { key: "estado", label: "Estado", render: (t) => {
      const [txt, tono] = ESTADO_TRANSACCION[t.estado] || [t.estado, "neutral"];
      return (
        <div>
          <Pill tono={tono}>{txt}</Pill>
          {t.motivo && <p className="text-xs text-gray-500 mt-1 max-w-xs">{t.motivo}</p>}
        </div>
      );
    } },
  ];

  return (
    <div className="space-y-4">
      <PageHeader titulo="Transacciones de los módulos"
                  descripcion="Los módulos mandan lo que pasó; el asiento se arma acá con la definición de cada tipo. Sin definición, la transacción espera.">
        <PermissionGate moduleCode="contabilidad" action="asientos:write">
          <Boton variante="secundario" onClick={volverAProcesar}>Volver a procesar</Boton>
        </PermissionGate>
        <PermissionGate moduleCode="contabilidad" action="definiciones:write">
          <Boton onClick={() => setDefiniendo({ nueva: true })}>＋ Definir un asiento</Boton>
        </PermissionGate>
      </PageHeader>

      <Alerta>{error}</Alerta>
      {ok && <Alerta tipo="ok">{ok}</Alerta>}

      <Kpis items={[
        { label: "Esperando definición", valor: datos.pendientes, tono: datos.pendientes ? "crit" : undefined },
        { label: "Con error", valor: datos.errores, tono: datos.errores ? "crit" : undefined },
        { label: "Tipos sin definir", valor: pendientes.length },
      ]} />

      {!cargando && pendientes.length === 0 && (
        <Alerta tipo="ok">
          No hay transacciones esperando definición. Cuando llegue un tipo nuevo, aparece acá con sus
          campos para que definas el asiento.
        </Alerta>
      )}

      {pendientes.length > 0 && (
        <Card>
          <h2 className="text-sm font-semibold text-gray-700 mb-2">Falta definir cómo se contabilizan</h2>
          <ul className="divide-y divide-gray-100">
            {pendientes.map((p) => (
              <li key={`${p.modulo}/${p.tipo}`} className="flex flex-wrap items-center gap-3 py-2">
                <div className="mr-auto">
                  <p className="font-medium text-gray-800">{p.tipo}</p>
                  <p className="text-xs text-gray-500">
                    {p.modulo} · {p.cantidad} transacción(es) · campos: {p.campos.join(", ") || "—"}
                  </p>
                </div>
                {puedeDefinir && <Boton onClick={() => setDefiniendo(p)}>Definir asiento</Boton>}
              </li>
            ))}
          </ul>
        </Card>
      )}

      <Card padding={false}>
        <Toolbar>
          <Field label="Estado">
            <select className="input" value={estado} onChange={(e) => setEstado(e.target.value)}>
              <option value="PENDIENTE_CONFIGURACION,ERROR">Sin contabilizar</option>
              <option value="CONTABILIZADA">Contabilizadas</option>
              <option value="">Todas</option>
            </select>
          </Field>
        </Toolbar>
        {cargando
          ? <p className="px-4 py-8 text-center text-sm text-gray-400">Cargando…</p>
          : <div className="p-4">
              <DataTable columns={columnas} rows={datos.items} rowKey={(t) => t.id} pageSize={25}
                         onRowClick={(t) => verTransaccion(t.id).then(setDetalle).catch((e) => setError(mensajeDeError(e)))}
                         emptyText="No hay transacciones con este filtro" />
            </div>}
      </Card>

      {definiendo && (
        <FormularioDefinicion pendiente={definiendo}
                              onCerrar={() => setDefiniendo(null)}
                              onListo={() => { setDefiniendo(null); setOk("Definición guardada: se contabilizaron las transacciones que esperaban."); cargar(); }} />
      )}

      {detalle && (
        <Modal titulo={`${detalle.tipo} · ${detalle.referencia}`} eyebrow={detalle.modulo}
               onClose={() => setDetalle(null)}
               footer={<>
                 {detalle.estado !== "CONTABILIZADA" && (
                   <PermissionGate moduleCode="contabilidad" action="definiciones:write">
                     <Boton onClick={() => { setDefiniendo({ modulo: detalle.modulo, tipo: detalle.tipo,
                                                             cantidad: 1, campos: Object.keys(detalle.datos || {}),
                                                             ejemplo: detalle }); setDetalle(null); }}>
                       Definir su asiento
                     </Boton>
                   </PermissionGate>
                 )}
                 <span className="flex-1" />
                 <Boton variante="secundario" onClick={() => setDetalle(null)}>Cerrar</Boton>
               </>}>
          <dl className="grid sm:grid-cols-3 gap-3 text-sm mb-3">
            <div><dt className="text-xs text-gray-500">Fecha</dt><dd className="font-medium">{fecha(detalle.fecha)}</dd></div>
            <div><dt className="text-xs text-gray-500">Estado</dt><dd className="font-medium">{ESTADO_TRANSACCION[detalle.estado]?.[0] || detalle.estado}</dd></div>
            <div><dt className="text-xs text-gray-500">Origen</dt><dd className="font-medium">{detalle.usuarioOrigen || "—"}</dd></div>
          </dl>
          {detalle.motivo && <div className="mb-3"><Alerta tipo="warn">{detalle.motivo}</Alerta></div>}
          <h3 className="text-sm font-semibold text-gray-700 mb-1">Lo que mandó el módulo</h3>
          <pre className="text-xs bg-gray-50 border border-gray-200 rounded-lg p-3 overflow-auto max-h-60">
            {JSON.stringify(detalle.datos, null, 2)}
          </pre>
          {detalle.asiento && (
            <>
              <h3 className="text-sm font-semibold text-gray-700 mt-3 mb-1">Asiento generado (N° {detalle.asiento.numero})</h3>
              <table className="w-full text-sm">
                <tbody className="divide-y divide-gray-100">
                  {detalle.asiento.lineas.map((l, i) => (
                    <tr key={i}>
                      <td className="py-1">{l.cuenta} · {l.nombre}</td>
                      <td className="py-1 text-right tabular-nums">{l.debe ? money(l.debe) : ""}</td>
                      <td className="py-1 text-right tabular-nums">{l.haber ? money(l.haber) : ""}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </Modal>
      )}
    </div>
  );
}
