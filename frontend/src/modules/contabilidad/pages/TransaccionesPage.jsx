import { useEffect, useState } from "react";
import {
  crearDefinicion, listarCuentas, listarDiarios, listarTransacciones, mensajeDeError, probarDefinicion,
  reprocesar, sinDefinir, verTransaccion,
} from "../../../api/contabilidad";
import { PermissionGate } from "../../../components/PrivateRoute";
import { useHasPermission } from "../../../context/usePermissions";
import { Alerta, Boton, Card, Field, Kpis, Modal, PageHeader, Toolbar } from "../../../components/ui";
import { DataTable } from "../../../components/ui/DataTable";
import { Pill } from "../../../components/ui/Pill";
import { ESTADO_TRANSACCION, fecha, money } from "../formato";

const VACIA = { dc: "DEBE", cuenta: "", importe: "", detalle: "" };

/** Alta de la definición que falta, con los campos que manda el módulo a mano. */
function DefinirAsiento({ pendiente, cuentas, diarios, onCerrar, onListo }) {
  const [nombre, setNombre] = useState(`${pendiente.tipo.replaceAll("_", " ").toLowerCase()}`);
  const [diario, setDiario] = useState("VAR");
  const [leyenda, setLeyenda] = useState(`${pendiente.tipo} {referencia}`);
  const [lineas, setLineas] = useState([{ ...VACIA }, { ...VACIA, dc: "HABER" }]);
  const [error, setError] = useState("");
  const [previa, setPrevia] = useState(null);
  const [guardando, setGuardando] = useState(false);
  const ejemplo = pendiente.ejemplo?.datos || {};

  const cambiar = (i, campo, v) => setLineas((ls) => ls.map((l, j) => (j === i ? { ...l, [campo]: v } : l)));

  const guardar = async (probar) => {
    setError(""); setPrevia(null); setGuardando(true);
    try {
      const d = await crearDefinicion({
        modulo: pendiente.modulo, tipo: pendiente.tipo, nombre, diario_codigo: diario, leyenda,
        lineas: lineas.filter((l) => l.cuenta && l.importe),
      });
      if (probar) {
        setPrevia(await probarDefinicion(d.id, ejemplo));
      }
      onListo(d);
    } catch (e) {
      setError(mensajeDeError(e, "No se pudo guardar la definición"));
    } finally {
      setGuardando(false);
    }
  };

  return (
    <Modal titulo={`Cómo se contabiliza «${pendiente.tipo}»`} eyebrow={`${pendiente.modulo} · ${pendiente.cantidad} transacción(es) esperando`}
           onClose={onCerrar} ancho="max-w-4xl"
           footer={<>
             <span className="text-xs text-gray-500 mr-auto">Al guardar se contabilizan las que estaban esperando.</span>
             <Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton>
             <Boton disabled={guardando} onClick={() => guardar(true)}>{guardando ? "Guardando…" : "Guardar y contabilizar"}</Boton>
           </>}>
      <div className="space-y-4">
        {error && <Alerta>{error}</Alerta>}
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-3">
          <p className="text-xs text-gray-500 mb-1">Campos que manda {pendiente.modulo} (usalos en los importes)</p>
          <div className="flex flex-wrap gap-2">
            {pendiente.campos.map((c) => (
              <code key={c} className="text-xs bg-surface border border-gray-200 rounded px-2 py-0.5">
                {c}{ejemplo[c] !== undefined ? ` = ${ejemplo[c]}` : ""}
              </code>
            ))}
          </div>
        </div>

        <div className="grid sm:grid-cols-3 gap-3">
          <Field label="Nombre"><input className="input w-full" value={nombre} onChange={(e) => setNombre(e.target.value)} /></Field>
          <Field label="Diario">
            <select className="input w-full" value={diario} onChange={(e) => setDiario(e.target.value)}>
              {diarios.map((d) => <option key={d.codigo} value={d.codigo}>{d.nombre}</option>)}
            </select>
          </Field>
          <Field label="Leyenda del asiento"><input className="input w-full" value={leyenda} onChange={(e) => setLeyenda(e.target.value)} /></Field>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[720px]">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50 text-left text-xs text-gray-500">
                <th className="px-3 py-2 font-medium">Lado</th>
                <th className="px-3 py-2 font-medium">Cuenta</th>
                <th className="px-3 py-2 font-medium">Importe</th>
                <th className="px-3 py-2 font-medium">Detalle</th>
                <th className="px-3 py-2" />
              </tr>
            </thead>
            <tbody>
              {lineas.map((l, i) => (
                <tr key={i} className="border-b border-gray-100">
                  <td className="px-3 py-1.5">
                    <select className="input" aria-label={`Lado ${i + 1}`} value={l.dc} onChange={(e) => cambiar(i, "dc", e.target.value)}>
                      <option value="DEBE">Debe</option><option value="HABER">Haber</option>
                    </select>
                  </td>
                  <td className="px-3 py-1.5">
                    <select className="input w-64" aria-label={`Cuenta ${i + 1}`} value={l.cuenta} onChange={(e) => cambiar(i, "cuenta", e.target.value)}>
                      <option value="">(elegir)</option>
                      {cuentas.map((c) => <option key={c.codigo} value={c.codigo}>{c.codigo} · {c.nombre}</option>)}
                    </select>
                  </td>
                  <td className="px-3 py-1.5">
                    <input className="input w-40" aria-label={`Importe ${i + 1}`} value={l.importe}
                           placeholder="capital + iva" onChange={(e) => cambiar(i, "importe", e.target.value)} />
                  </td>
                  <td className="px-3 py-1.5">
                    <input className="input w-full" aria-label={`Detalle ${i + 1}`} value={l.detalle} onChange={(e) => cambiar(i, "detalle", e.target.value)} />
                  </td>
                  <td className="px-3 py-1.5 text-right">
                    <button type="button" aria-label={`Quitar línea ${i + 1}`} className="text-gray-400 hover:text-red-600"
                            onClick={() => setLineas((ls) => (ls.length > 2 ? ls.filter((_, j) => j !== i) : ls))}>✕</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <Boton type="button" variante="secundario" onClick={() => setLineas((ls) => [...ls, { ...VACIA }])}>
          ＋ Agregar línea
        </Boton>

        {previa && (
          <div className="border border-green-200 bg-green-50 rounded-lg p-3">
            <p className="text-sm font-medium text-green-800 mb-1">Así queda el asiento con la transacción de ejemplo</p>
            <ul className="text-sm text-gray-700">
              {previa.lineas.map((l, i) => (
                <li key={i} className="tabular-nums">
                  {l.cuenta} {l.nombre} · {l.debe ? `debe ${money(l.debe)}` : `haber ${money(l.haber)}`}
                </li>
              ))}
            </ul>
            <p className="text-xs text-gray-600 mt-1">Total debe {money(previa.debe)} · haber {money(previa.haber)}</p>
          </div>
        )}
      </div>
    </Modal>
  );
}

export default function TransaccionesPage() {
  const puedeDefinir = useHasPermission("contabilidad", "definiciones:write");
  const [pendientes, setPendientes] = useState([]);
  const [datos, setDatos] = useState({ items: [], total: 0, pendientes: 0, errores: 0 });
  const [estado, setEstado] = useState("PENDIENTE_CONFIGURACION,ERROR");
  const [cuentas, setCuentas] = useState([]);
  const [diarios, setDiarios] = useState([]);
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

  useEffect(() => {
    if (!puedeDefinir) return;
    listarCuentas({ solo_imputables: true }).then((d) => setCuentas(d.items)).catch(() => {});
    listarDiarios().then((d) => setDiarios(d.items)).catch(() => {});
  }, [puedeDefinir]);

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
      </PageHeader>

      <Alerta>{error}</Alerta>
      {ok && <Alerta tipo="ok">{ok}</Alerta>}

      <Kpis items={[
        { label: "Esperando definición", valor: datos.pendientes, tono: datos.pendientes ? "crit" : undefined },
        { label: "Con error", valor: datos.errores, tono: datos.errores ? "crit" : undefined },
        { label: "Tipos sin definir", valor: pendientes.length },
      ]} />

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
        <DefinirAsiento pendiente={definiendo} cuentas={cuentas} diarios={diarios}
                        onCerrar={() => setDefiniendo(null)}
                        onListo={() => { setDefiniendo(null); setOk("Definición guardada: se contabilizaron las transacciones que esperaban."); cargar(); }} />
      )}

      {detalle && (
        <Modal titulo={`${detalle.tipo} · ${detalle.referencia}`} eyebrow={detalle.modulo}
               onClose={() => setDetalle(null)}
               footer={<><span className="flex-1" /><Boton variante="secundario" onClick={() => setDetalle(null)}>Cerrar</Boton></>}>
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
