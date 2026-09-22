import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus } from "lucide-react";
import { listarLotes, mensajeDeError } from "../../../api/tesoreria";
import { PermissionGate } from "../../../components/PrivateRoute";
import { Alerta, Boton, Card, Field, Kpis, LimpiarFiltros, PageHeader, Toolbar } from "../../../components/ui";
import { DataTable } from "../../../components/ui/DataTable";
import { Pill } from "../../../components/ui/Pill";
import { ESTADO_LOTE, ORIGENES, fechaHora, money } from "../estados";

const FILTROS_ESTADO = {
  "": "Todos",
  "PENDIENTE_APROBACION,APROBADO": "Por aprobar o enviar",
  "ENVIADO,CON_ERRORES": "En curso o con errores",
  CONFIRMADO: "Acreditados",
  RECHAZADO: "Rechazados",
};

const COLUMNAS = [
  { key: "codigo", label: "Lote", sortable: true, render: (l) => (
    <div>
      <p className="font-medium text-gray-800">{l.codigo}</p>
      <p className="text-xs text-gray-400">{l.descripcion || l.referencia_origen}</p>
    </div>
  ) },
  { key: "origen", label: "Origen", sortable: true, render: (l) => ORIGENES[l.origen] || l.origen },
  { key: "creado_en", label: "Recibido", sortable: true, render: (l) => fechaHora(l.creado_en) },
  { key: "cantidad", label: "Pagos", align: "right", sortable: true,
    render: (l) => <span className="tabular-nums">{l.cantidad}{l.excluidos ? ` (+${l.excluidos} excl.)` : ""}</span> },
  { key: "total", label: "Total", align: "right", sortable: true, render: (l) => <span className="tabular-nums">{money(l.total)}</span> },
  { key: "estado", label: "Estado", render: (l) => {
    const [txt, tono] = ESTADO_LOTE[l.estado] || [l.estado, "neutral"];
    return (
      <div className="flex flex-wrap gap-1">
        <Pill tono={tono}>{txt}</Pill>
        {l.simulado && <Pill>Simulado</Pill>}
      </div>
    );
  } },
];

export default function LotesPage() {
  const navigate = useNavigate();
  const [datos, setDatos] = useState({ items: [], pendientes: 0, envio_simulado: false });
  const [estado, setEstado] = useState("PENDIENTE_APROBACION,APROBADO");
  const [origen, setOrigen] = useState("");
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    setCargando(true);
    setError("");
    listarLotes({ ...(estado && { estado }), ...(origen && { origen }) })
      .then(setDatos)
      .catch((e) => setError(mensajeDeError(e, "No se pudieron cargar los lotes")))
      .finally(() => setCargando(false));
  }, [estado, origen]);

  const total = datos.items.reduce((s, l) => s + l.total, 0);

  return (
    <div className="space-y-4">
      <PageHeader titulo="Lotes de pagos"
                  descripcion="Pagos que llegan de Créditos, Conciliación o carga manual: se revisan, se aprueban y se envían por Interbanking.">
        <PermissionGate moduleCode="tesoreria" action="lotes:write">
          <Boton onClick={() => navigate("/modules/tesoreria/nuevo")} className="flex items-center gap-2">
            <Plus size={16} /> Nuevo lote
          </Boton>
        </PermissionGate>
      </PageHeader>

      {datos.envio_simulado && (
        <Alerta tipo="warn">
          Modo simulación: los envíos se registran pero no mueven dinero. Se desactiva con TESORERIA_ENVIO_SIMULADO=false.
        </Alerta>
      )}
      <Alerta>{error}</Alerta>

      <Kpis items={[
        { label: "Por aprobar o enviar", valor: datos.pendientes, tono: datos.pendientes ? "crit" : undefined },
        { label: "Lotes en la vista", valor: datos.items.length },
        { label: "Total de la vista", valor: money(total) },
      ]} />

      <Card padding={false}>
        <Toolbar>
          <Field label="Estado">
            <select className="input" value={estado} onChange={(e) => setEstado(e.target.value)}>
              {Object.entries(FILTROS_ESTADO).map(([v, t]) => <option key={v} value={v}>{t}</option>)}
            </select>
          </Field>
          <Field label="Origen">
            <select className="input" value={origen} onChange={(e) => setOrigen(e.target.value)}>
              <option value="">Todos</option>
              {Object.entries(ORIGENES).map(([v, t]) => <option key={v} value={v}>{t}</option>)}
            </select>
          </Field>
          <LimpiarFiltros activo={!!estado || !!origen} onClear={() => { setEstado(""); setOrigen(""); }} />
        </Toolbar>
        {cargando
          ? <p className="px-4 py-8 text-center text-gray-400 text-sm">Cargando…</p>
          : <DataTable columns={COLUMNAS} rows={datos.items} rowKey={(l) => l.id} pageSize={25}
                       onRowClick={(l) => navigate(`/modules/tesoreria/lotes/${l.id}`)}
                       emptyText="No hay lotes con estos filtros" />}
      </Card>
    </div>
  );
}
