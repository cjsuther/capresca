import { useEffect, useState } from "react";
import { creditos } from "../../../../api/creditos";
import { DataTable } from "../../components/DataTable";
import { PageHeader, Card, Toolbar, Field, Boton, Alerta } from "../../components/ui";
import { money, fecha, num } from "../../components/format";

const LIMIT = 25;

const COLS = [
  { key: "fecha_pago", label: "Fecha pago", render: (r) => fecha(r.fecha_pago) },
  { key: "credito_id", label: "Crédito" },
  { key: "cuota", label: "Cuota" },
  { key: "cliente", label: "Cliente" },
  { key: "nro_recibo", label: "Recibo" },
  { key: "via_pago", label: "Vía" },
  { key: "cajero", label: "Cajero" },
  { key: "total_pagado", label: "Pagado", align: "right", render: (r) => money(r.total_pagado) },
];

export default function PagosEnCajaPage() {
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [credito, setCredito] = useState("");
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [totalPagado, setTotalPagado] = useState(0);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState("");

  const filtros = () => ({
    desde: desde || undefined, hasta: hasta || undefined,
    credito_id: credito ? Number(credito) : undefined,
  });

  async function cargar(off = 0) {
    setError("");
    try {
      const d = await creditos.pagosEnCaja({ ...filtros(), limit: LIMIT, offset: off });
      setRows(d.items); setTotal(d.total); setTotalPagado(d.total_pagado); setOffset(off);
    } catch (e) { setError(e.message); }
  }
  useEffect(() => { cargar(0); }, []);

  return (
    <>
      <PageHeader
        titulo="Pagos de créditos en caja"
        descripcion="Cuotas efectivamente pagadas, con recibo, vía de pago y cajero."
      />

      {error && <div className="mb-4"><Alerta>{error}</Alerta></div>}

      <Card padding={false}>
        <Toolbar>
          <Field label="Desde">
            <input type="date" className="input" value={desde} onChange={(e) => setDesde(e.target.value)} />
          </Field>
          <Field label="Hasta">
            <input type="date" className="input" value={hasta} onChange={(e) => setHasta(e.target.value)} />
          </Field>
          <Field label="N° crédito">
            <input className="input w-32" value={credito} onChange={(e) => setCredito(e.target.value)} />
          </Field>
          <Boton onClick={() => cargar(0)}>Filtrar</Boton>
          <Boton variante="ok" onClick={() => creditos.descargarPagosEnCajaExcel(filtros())}>Descargar Excel</Boton>
          <span className="ml-auto text-sm text-gray-500">
            {num(total)} pagos · cobrado <b>{money(totalPagado || 0)}</b>
          </span>
        </Toolbar>
        <div className="p-4">
          <DataTable columns={COLS} rows={rows} total={total} limit={LIMIT} offset={offset}
                     onPage={(off) => cargar(off)} rowKey={(r, i) => `${r.credito_id}-${r.cuota}-${i}`}
                     emptyText="Sin pagos en el período" />
        </div>
      </Card>
    </>
  );
}
