import { useEffect, useState } from "react";
import {
  borrarExtracto, cargarExtracto, conciliar, conciliarAutomatica, desconciliar, listarCuentas,
  mensajeDeError, verConciliacion,
} from "../../../api/contabilidad";
import { PermissionGate } from "../../../components/PrivateRoute";
import { useHasPermission } from "../../../context/usePermissions";
import { Alerta, Boton, Card, Field, Kpis, PageHeader, Toolbar } from "../../../components/ui";
import { Confirmacion } from "../../../components/ui/Confirmacion";
import { DataTable } from "../../../components/ui/DataTable";
import { Pill } from "../../../components/ui/Pill";
import { fecha, hoy, money } from "../formato";

const VACIO = { fecha: hoy(), importe: "", descripcion: "", referencia: "" };

/**
 * Conciliación bancaria: el extracto del banco contra el mayor de la cuenta. Se elige una línea del
 * extracto y se la vincula con su movimiento; lo que queda suelto de cada lado es la diferencia.
 */
export default function ConciliacionPage() {
  const puedeConciliar = useHasPermission("contabilidad", "asientos:write");
  const [cuentas, setCuentas] = useState([]);
  const [cuenta, setCuenta] = useState("1.1.02");
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [datos, setDatos] = useState(null);
  const [sel, setSel] = useState(null);
  const [nuevo, setNuevo] = useState(VACIO);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [borrando, setBorrando] = useState(null);

  useEffect(() => {
    listarCuentas({ solo_imputables: true })
      .then((d) => setCuentas(d.items.filter((c) => /caja|banco/i.test(c.nombre))))
      .catch(() => {});
  }, []);

  const cargar = () => {
    setError(""); setSel(null);
    verConciliacion({ cuenta, ...(desde && { desde }), ...(hasta && { hasta }) })
      .then(setDatos)
      .catch((e) => setError(mensajeDeError(e)));
  };
  useEffect(cargar, [cuenta, desde, hasta]);   // eslint-disable-line react-hooks/exhaustive-deps

  const agregar = async () => {
    setError("");
    try {
      await cargarExtracto({ cuenta_codigo: cuenta, fecha: nuevo.fecha, importe: Number(nuevo.importe),
                             descripcion: nuevo.descripcion, referencia: nuevo.referencia });
      setNuevo(VACIO); cargar();
    } catch (e) { setError(mensajeDeError(e)); }
  };

  const vincular = async (mov) => {
    if (!sel) { setError("Elegí primero una línea del extracto."); return; }
    setError("");
    try { await conciliar(sel.id, mov.asientoLineaId); setOk("Conciliada."); cargar(); }
    catch (e) { setError(mensajeDeError(e)); }
  };

  const automatica = async () => {
    setError("");
    try {
      const r = await conciliarAutomatica(cuenta);
      setOk(`${r.conciliadas} par(es) conciliado(s) automáticamente.`);
      cargar();
    } catch (e) { setError(mensajeDeError(e)); }
  };

  return (
    <div className="space-y-4">
      <PageHeader titulo="Conciliación bancaria"
                  descripcion="El extracto del banco contra el mayor de la cuenta. Lo que queda sin pareja es la diferencia a explicar.">
        <PermissionGate moduleCode="contabilidad" action="asientos:write">
          <Boton variante="secundario" onClick={automatica}>Conciliar automáticamente</Boton>
        </PermissionGate>
      </PageHeader>

      <Alerta>{error}</Alerta>
      {ok && <Alerta tipo="ok">{ok}</Alerta>}

      <Card padding={false}>
        <Toolbar>
          <Field label="Cuenta">
            <select className="input w-64" value={cuenta} onChange={(e) => setCuenta(e.target.value)}>
              {cuentas.map((c) => <option key={c.codigo} value={c.codigo}>{c.codigo} · {c.nombre}</option>)}
            </select>
          </Field>
          <Field label="Desde"><input type="date" className="input" value={desde} onChange={(e) => setDesde(e.target.value)} /></Field>
          <Field label="Hasta"><input type="date" className="input" value={hasta} onChange={(e) => setHasta(e.target.value)} /></Field>
        </Toolbar>
      </Card>

      {datos && (
        <Kpis items={[
          { label: "Saldo del extracto", valor: money(datos.totales.saldoExtracto) },
          { label: "Saldo del mayor", valor: money(datos.totales.saldoMayor) },
          { label: "Diferencia", valor: money(datos.totales.diferencia),
            tono: datos.totales.diferencia === 0 ? "ok" : "crit" },
          { label: "Conciliadas", valor: datos.totales.conciliadas },
        ]} />
      )}

      <div className="grid lg:grid-cols-2 gap-4">
        <Card padding={false}>
          <div className="px-4 py-3 border-b border-gray-200">
            <h2 className="text-sm font-semibold text-gray-700">Extracto del banco</h2>
            <p className="text-xs text-gray-500">Elegí una línea y después su movimiento en el mayor.</p>
          </div>
          {puedeConciliar && (
            <div className="flex flex-wrap items-end gap-2 px-4 py-3 border-b border-gray-200">
              <Field label="Fecha"><input type="date" className="input" value={nuevo.fecha} onChange={(e) => setNuevo({ ...nuevo, fecha: e.target.value })} /></Field>
              <Field label="Importe (+ entra / − sale)">
                <input className="input w-32 text-right" aria-label="Importe del extracto" value={nuevo.importe}
                       onChange={(e) => setNuevo({ ...nuevo, importe: e.target.value })} />
              </Field>
              <Field label="Descripción">
                <input className="input w-48" value={nuevo.descripcion} onChange={(e) => setNuevo({ ...nuevo, descripcion: e.target.value })} />
              </Field>
              <Boton disabled={!nuevo.importe} onClick={agregar}>Agregar</Boton>
            </div>
          )}
          <div className="p-4">
            <DataTable rowKey={(e) => e.id} rows={datos?.extracto || []} pageSize={25}
              onRowClick={(e) => !e.conciliada && setSel(sel?.id === e.id ? null : e)}
              rowClass={(e) => (sel?.id === e.id ? "bg-blue-50" : "")}
              columns={[
                { key: "fecha", label: "Fecha", render: (e) => fecha(e.fecha) },
                { key: "descripcion", label: "Descripción" },
                { key: "importe", label: "Importe", align: "right", render: (e) => money(e.importe) },
                { key: "estado", label: "Estado", render: (e) => (
                  sel?.id === e.id ? <Pill tono="brand">seleccionada</Pill>
                    : e.conciliada ? <Pill tono="ok">conciliada</Pill> : <Pill tono="warn">pendiente</Pill>) },
                ...(puedeConciliar ? [{ key: "acciones", label: "", align: "right", render: (e) => (
                  e.conciliada
                    ? <button className="text-xs text-gray-500 hover:text-gray-800" onClick={(ev) => { ev.stopPropagation(); desconciliar(e.id).then(cargar); }}>Desconciliar</button>
                    : <button className="text-xs text-red-500 hover:text-red-700" aria-label={`Borrar línea del ${e.fecha}`}
                              onClick={(ev) => { ev.stopPropagation(); setBorrando(e); }}>✕</button>
                ) }] : []),
              ]} emptyText="Cargá el extracto del banco" />
          </div>
        </Card>

        <Card padding={false}>
          <div className="px-4 py-3 border-b border-gray-200">
            <h2 className="text-sm font-semibold text-gray-700">Movimientos del mayor</h2>
            <p className="text-xs text-gray-500">
              {sel ? `Elegí el movimiento de ${money(sel.importe)} que corresponde` : "La contabilidad de esta cuenta"}
            </p>
          </div>
          <div className="p-4">
            <DataTable rowKey={(m) => m.asientoLineaId} rows={datos?.movimientos || []} pageSize={25}
              onRowClick={(m) => puedeConciliar && !m.conciliada && vincular(m)}
              columns={[
                { key: "fecha", label: "Fecha", render: (m) => fecha(m.fecha) },
                { key: "numero", label: "Asiento", align: "right" },
                { key: "concepto", label: "Concepto" },
                { key: "importe", label: "Importe", align: "right", render: (m) => money(m.importe) },
                { key: "estado", label: "Estado", render: (m) => (
                  m.conciliada ? <Pill tono="ok">conciliada</Pill> : <Pill tono="warn">pendiente</Pill>) },
              ]} emptyText="La cuenta no tuvo movimientos" />
          </div>
        </Card>
      </div>

      {borrando && (
        <Confirmacion titulo="Borrar la línea del extracto" confirmar="Borrar"
                      mensaje={`${fecha(borrando.fecha)} · ${money(borrando.importe)}\n${borrando.descripcion || ""}`}
                      onConfirmar={() => { borrarExtracto(borrando.id).then(() => { setBorrando(null); cargar(); }); }}
                      onCancelar={() => setBorrando(null)} />
      )}
    </div>
  );
}
