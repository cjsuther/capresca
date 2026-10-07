import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus } from "lucide-react";
import { listarOrdenes, mensajeDeError } from "../../../api/tesoreria";
import { PermissionGate } from "../../../components/PrivateRoute";
import { Alerta, Boton, Card, Field, PageHeader, Toolbar } from "../../../components/ui";
import { DataTable } from "../../../components/ui/DataTable";
import { Pill } from "../../../components/ui/Pill";
import { ESTADO_ORDEN, fechaHora, money } from "../estados";

const FILTROS = { CONFECCIONADA: "Vigentes", ANULADA: "Anuladas", "": "Todas" };

const COLUMNAS = [
  { key: "codigo", label: "Orden de pago", sortable: true, render: (o) => (
    <div>
      <p className="font-medium text-gray-800 tabular-nums">{o.codigo}</p>
      <p className="text-xs text-gray-400">{o.actos_texto}</p>
    </div>
  ) },
  { key: "lotes", label: "Lotes de créditos", render: (o) => <span className="text-sm text-gray-600">{o.lotes.join(", ")}</span> },
  { key: "creado_en", label: "Confeccionada", sortable: true,
    render: (o) => <span className="text-sm">{fechaHora(o.creado_en)}<span className="text-gray-400"> · {o.creado_por}</span></span> },
  { key: "cantidad", label: "Transferencias", align: "right", sortable: true, render: (o) => <span className="tabular-nums">{o.cantidad}</span> },
  { key: "importe", label: "Importe", align: "right", sortable: true, render: (o) => <span className="tabular-nums">{money(o.importe)}</span> },
  { key: "estado_pago", label: "Estado", render: (o) => {
    const [txt, tono] = ESTADO_ORDEN[o.estado_pago] || [o.estado_pago, "neutral"];
    return <Pill tono={tono}>{txt}</Pill>;
  } },
];

/**
 * Órdenes de pago de créditos: cada una junta resoluciones / disposiciones de Despacho con sus lotes de
 * Créditos. Al confeccionarla los lotes quedan "para liquidar"; el tesorero aprueba y paga su lote de
 * pagos por Interbanking y, acreditadas las transferencias, los lotes quedan liquidados.
 */
export default function OrdenesPagoPage() {
  const navigate = useNavigate();
  const [estado, setEstado] = useState("CONFECCIONADA");
  const [items, setItems] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    setCargando(true); setError("");
    listarOrdenes(estado ? { estado } : {})
      .then((d) => setItems(d.items))
      .catch((e) => setError(mensajeDeError(e, "No se pudieron cargar las órdenes de pago")))
      .finally(() => setCargando(false));
  }, [estado]);

  return (
    <div className="space-y-4">
      <PageHeader titulo="Órdenes de pago"
                  descripcion="Resoluciones y disposiciones de créditos con sus lotes. Al confeccionar la orden, los lotes quedan para liquidar; el tesorero la aprueba y hace las transferencias por Interbanking, y acreditadas, los lotes quedan liquidados.">
        <PermissionGate moduleCode="tesoreria" action="lotes:write">
          <Boton onClick={() => navigate("/modules/tesoreria/ordenes/nueva")} className="flex items-center gap-2">
            <Plus size={16} /> Nueva orden de pago
          </Boton>
        </PermissionGate>
      </PageHeader>
      <Alerta>{error}</Alerta>
      <Card padding={false}>
        <Toolbar>
          <Field label="Estado">
            <select className="input" value={estado} aria-label="Estado" onChange={(e) => setEstado(e.target.value)}>
              {Object.entries(FILTROS).map(([v, t]) => <option key={v} value={v}>{t}</option>)}
            </select>
          </Field>
        </Toolbar>
        {cargando
          ? <p className="px-4 py-8 text-center text-gray-400 text-sm">Cargando…</p>
          : <DataTable columns={COLUMNAS} rows={items} rowKey={(o) => o.id} pageSize={25}
                       onRowClick={(o) => navigate(`/modules/tesoreria/ordenes/${o.id}`)}
                       emptyText="No hay órdenes de pago" />}
      </Card>
    </div>
  );
}
