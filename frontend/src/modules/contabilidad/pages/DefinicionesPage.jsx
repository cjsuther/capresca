import { useEffect, useState } from "react";
import { listarDefiniciones, mensajeDeError } from "../../../api/contabilidad";
import { PermissionGate } from "../../../components/PrivateRoute";
import { useHasPermission } from "../../../context/usePermissions";
import { Alerta, Boton, Card, Field, PageHeader, Toolbar } from "../../../components/ui";
import { DataTable } from "../../../components/ui/DataTable";
import { Pill } from "../../../components/ui/Pill";
import { FormularioDefinicion } from "../components/FormularioDefinicion";
import { fecha } from "../formato";

/**
 * Definiciones de asiento: la regla que convierte cada tipo de transacción de un módulo en su asiento.
 * Sin la definición, la transacción queda esperando (ver la pantalla Transacciones).
 */
export default function DefinicionesPage() {
  const puedeDefinir = useHasPermission("contabilidad", "definiciones:write");
  const [items, setItems] = useState([]);
  const [modulo, setModulo] = useState("");
  const [editando, setEditando] = useState(null);   // definición | {nueva: true}
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");

  const cargar = () => {
    setCargando(true);
    listarDefiniciones(modulo)
      .then((d) => setItems(d.items))
      .catch((e) => setError(mensajeDeError(e)))
      .finally(() => setCargando(false));
  };
  useEffect(cargar, [modulo]);   // eslint-disable-line react-hooks/exhaustive-deps

  const modulos = [...new Set(items.map((d) => d.modulo))];

  const columnas = [
    { key: "modulo", label: "Módulo", sortable: true },
    { key: "tipo", label: "Transacción", sortable: true, render: (d) => (
      <div><p className="font-medium text-gray-800">{d.tipo}</p><p className="text-xs text-gray-400">{d.nombre}</p></div>
    ) },
    { key: "diario", label: "Diario" },
    { key: "lineas", label: "Asiento", render: (d) => (
      <ul className="text-xs text-gray-600">
        {(d.lineas || []).map((l, i) => (
          <li key={i}>{l.dc === "DEBE" ? "D" : "H"} · {l.cuenta} · <code>{l.importe}</code></li>
        ))}
      </ul>
    ) },
    { key: "vigencia", label: "Vigencia", render: (d) => (
      d.vigenteDesde || d.vigenteHasta
        ? `${d.vigenteDesde ? fecha(d.vigenteDesde) : "—"} a ${d.vigenteHasta ? fecha(d.vigenteHasta) : "—"}`
        : "siempre"
    ) },
    { key: "activa", label: "Estado", render: (d) => (
      d.activa ? <Pill tono="ok">activa</Pill> : <Pill>inactiva</Pill>) },
  ];

  return (
    <div className="space-y-4">
      <PageHeader titulo="Definiciones de asiento"
                  descripcion="Cómo se contabiliza cada tipo de transacción: qué cuenta va al debe, cuál al haber y cómo se calcula el importe con los datos que manda el módulo.">
        <PermissionGate moduleCode="contabilidad" action="definiciones:write">
          <Boton onClick={() => setEditando({ nueva: true })}>＋ Nueva definición</Boton>
        </PermissionGate>
      </PageHeader>

      <Alerta>{error}</Alerta>
      {ok && <Alerta tipo="ok">{ok}</Alerta>}

      <Card padding={false}>
        <Toolbar>
          <Field label="Módulo">
            <select className="input" value={modulo} onChange={(e) => setModulo(e.target.value)}>
              <option value="">Todos</option>
              {modulos.map((m) => <option key={m} value={m}>{m}</option>)}
            </select>
          </Field>
          <span className="ml-auto text-sm text-gray-500">{items.length} definición(es)</span>
        </Toolbar>
        {cargando
          ? <p className="px-4 py-8 text-center text-sm text-gray-400">Cargando…</p>
          : <div className="p-4">
              <DataTable columns={columnas} rows={items} rowKey={(d) => d.id} pageSize={25}
                         onRowClick={(d) => puedeDefinir && setEditando(d)}
                         emptyText="Todavía no hay definiciones. Creá una o definila desde una transacción que esté esperando." />
            </div>}
      </Card>

      {editando && (
        <FormularioDefinicion definicion={editando.nueva ? null : editando}
                              onCerrar={() => setEditando(null)}
                              onListo={(d) => {
                                setEditando(null);
                                const r = d.reproceso;
                                setOk(r?.contabilizadas
                                  ? `Definición guardada: se contabilizaron ${r.contabilizadas} transacción(es).`
                                  : "Definición guardada.");
                                cargar();
                              }} />
      )}
    </div>
  );
}
