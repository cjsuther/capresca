import { useEffect, useState } from "react";
import { creditos } from "../../../../api/creditos";
import { DataTable } from "../../components/DataTable";
import { PageHeader, Card, Field, Boton, Alerta, Modal } from "../../components/ui";
import { Pill } from "../../components/Pill";
import { BuscadorCliente, nombreCliente } from "../../components/BuscadorCliente";
import { usePuedeEscribir } from "../../permisos";
import { money, fecha, hoy } from "../../components/format";

const ESTADOS = { I: "Ingresada", A: "Aprobada", O: "Otorgada", B: "Baja" };
const TONO = { I: "warn", A: "brand", O: "ok", B: "neutral" };

const COLS_CUOTAS = [
  { key: "numero", label: "#" },
  { key: "fecha_vencimiento", label: "Vto", render: (c) => fecha(c.fecha_vencimiento) },
  { key: "saldo_capital", label: "Saldo", align: "right", render: (c) => money(c.saldo_capital) },
  { key: "amortizacion", label: "Capital", align: "right", render: (c) => money(c.amortizacion) },
  { key: "interes", label: "Interés", align: "right", render: (c) => money(c.interes) },
  { key: "iva_interes", label: "IVA", align: "right", render: (c) => money(c.iva_interes) },
  { key: "total", label: "Total", align: "right", render: (c) => <b>{money(c.total)}</b> },
];

export default function SolicitudesPage() {
  const puedeEscribir = usePuedeEscribir();
  const [cliente, setCliente] = useState(null);
  const [lineas, setLineas] = useState([]);
  const [solicitudes, setSolicitudes] = useState([]);
  const [detalle, setDetalle] = useState(null);
  const [credito, setCredito] = useState(null);
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    linea_id: 0, monto_solicitado: "300000", cantidad_cuotas: 12,
    fecha_primer_vencimiento: hoy(), cuota_fija: "", garante1_cuil: "",
  });

  const refrescar = () => creditos.solicitudes().then(setSolicitudes).catch((e) => setError(e.message));

  useEffect(() => {
    creditos.lineas().then((l) => {
      setLineas(l);
      if (l.length) setForm((f) => ({ ...f, linea_id: l[0].id }));
    }).catch((e) => setError(e.message));
    refrescar();
  }, []);

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const lineaSel = lineas.find((l) => l.id === Number(form.linea_id));
  const esCuotaFija = lineaSel?.tipo_calculo === 5;

  async function crear(e) {
    e.preventDefault();
    setError(""); setCredito(null);
    if (!cliente) { setError("Elegí el cliente en el padrón."); return; }
    const payload = {
      cliente_id: cliente.id, linea_id: Number(form.linea_id),
      monto_solicitado: form.monto_solicitado,
      cantidad_cuotas: Number(form.cantidad_cuotas),
      fecha_primer_vencimiento: form.fecha_primer_vencimiento,
      garante1_cuil: form.garante1_cuil,
      ...(esCuotaFija ? { cuota_fija: form.cuota_fija } : {}),
    };
    try {
      setDetalle(await creditos.crearSolicitud(payload));
      refrescar();
    } catch (err) { setError(err.message); }
  }

  async function verDetalle(id) {
    setCredito(null); setError("");
    try { setDetalle(await creditos.solicitud(id)); }
    catch (e) { setError(e.message); }
  }

  async function otorgar(id, forzar = false) {
    setError("");
    try {
      setCredito(await creditos.otorgar(id, forzar));
      setDetalle(await creditos.solicitud(id));
      refrescar();
    } catch (err) { setError(err.message); }
  }

  const COLS = [
    { key: "id", label: "#", sortable: true, align: "right" },
    { key: "cliente_nombre", label: "Cliente", sortable: true,
      render: (s) => s.cliente_nombre || s.cliente_id },
    { key: "monto_solicitado", label: "Monto", sortable: true, align: "right",
      sortValue: (s) => Number(s.monto_solicitado), render: (s) => money(s.monto_solicitado) },
    { key: "cantidad_cuotas", label: "Cuotas", sortable: true, align: "right" },
    { key: "estado", label: "Estado", sortable: true,
      render: (s) => <Pill tono={TONO[s.estado]}>{ESTADOS[s.estado] || s.estado}</Pill> },
  ];

  const cerrar = () => { setDetalle(null); setCredito(null); };

  return (
    <>
      <PageHeader
        titulo="Solicitudes"
        descripcion="Alta de solicitudes sobre las líneas de crédito y otorgamiento del préstamo."
      />

      {error && <div className="mb-4"><Alerta>{error}</Alerta></div>}

      {puedeEscribir && (
        <Card className="mb-4">
          <h2 className="font-semibold text-gray-800 mb-3">Nueva solicitud de crédito</h2>
          <form onSubmit={crear} className="grid gap-3 sm:grid-cols-3">
            <Field label="Cliente" className="sm:col-span-2">
              <BuscadorCliente seleccionado={cliente} onSelect={setCliente} />
            </Field>
            <Field label="Línea">
              <select className="input w-full" value={form.linea_id} onChange={set("linea_id")}>
                {lineas.map((l) => <option key={l.id} value={l.id}>{l.nombre}</option>)}
              </select>
            </Field>
            <Field label="Monto">
              <input className="input w-full" value={form.monto_solicitado} onChange={set("monto_solicitado")} />
            </Field>
            <Field label={esCuotaFija ? "Plazo (lo recalcula el motor)" : "Cuotas"}>
              <input type="number" className="input w-full" value={form.cantidad_cuotas}
                     onChange={set("cantidad_cuotas")} disabled={esCuotaFija} />
            </Field>
            {esCuotaFija && (
              <Field label="Cuota fija">
                <input className="input w-full" value={form.cuota_fija} onChange={set("cuota_fija")} />
              </Field>
            )}
            <Field label="1er vencimiento">
              <input type="date" className="input w-full" value={form.fecha_primer_vencimiento}
                     onChange={set("fecha_primer_vencimiento")} />
            </Field>
            <Field label="Garante (CUIL)">
              <input className="input w-full" value={form.garante1_cuil} onChange={set("garante1_cuil")} />
            </Field>
            <div className="sm:col-span-3">
              <Boton type="submit">Registrar solicitud</Boton>
            </div>
          </form>
        </Card>
      )}

      <Card padding={false}>
        <p className="px-4 py-3 text-sm text-gray-500 border-b border-gray-200">
          {solicitudes.length} solicitudes · clickeá una para ver el detalle
        </p>
        <div className="p-4">
          <DataTable columns={COLS} rows={solicitudes} rowKey={(s) => s.id}
                     onRowClick={(s) => verDetalle(s.id)}
                     clientSort pageSize={25} defaultSort="id" emptyText="Sin solicitudes" />
        </div>
      </Card>

      {detalle && (
        <Modal
          eyebrow={`Solicitud #${detalle.id} · ${ESTADOS[detalle.estado] || detalle.estado}`}
          titulo={detalle.cliente_nombre || nombreCliente(cliente)}
          onClose={cerrar}
          footer={
            <>
              <Boton variante="secundario" onClick={cerrar}>Cerrar</Boton>
              <span className="flex-1" />
              {puedeEscribir && detalle.estado === "I" && (
                <>
                  {!detalle.puede_otorgarse && (
                    <Boton variante="danger" onClick={() => otorgar(detalle.id, true)}>Otorgar igual (forzar)</Boton>
                  )}
                  <Boton disabled={!detalle.puede_otorgarse} onClick={() => otorgar(detalle.id)}>Otorgar crédito</Boton>
                </>
              )}
            </>
          }
        >
          <p className="text-sm text-gray-600">
            {detalle.linea_nombre} · {money(detalle.monto_solicitado)} · {detalle.cantidad_cuotas} cuotas
            {detalle.margen_disponible != null && <> · Margen: <b>{money(detalle.margen_disponible)}</b></>}
          </p>

          {detalle.advertencias?.map((a, i) => (
            <div className="mt-3" key={i}><Alerta tipo="warn">{a}</Alerta></div>
          ))}

          {detalle.credito_id && (
            <div className="mt-3"><Alerta tipo="ok">Crédito otorgado N° {detalle.credito_id}</Alerta></div>
          )}

          {credito && (
            <div className="mt-4">
              <p className="text-sm font-medium text-gray-800 mb-2">
                Crédito N° {credito.id} — plan de {credito.cantidad_cuotas} cuotas · total {money(credito.total_a_pagar)}
              </p>
              <DataTable columns={COLS_CUOTAS} rows={credito.cuotas} rowKey={(c) => c.numero}
                         pageSize={12} emptyText="El crédito no tiene cuotas" />
            </div>
          )}
        </Modal>
      )}
    </>
  );
}
