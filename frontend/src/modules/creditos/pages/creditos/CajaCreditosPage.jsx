import { useEffect, useMemo, useState } from "react";
import { creditos } from "../../../../api/creditos";
import { PageHeader, Card, Field, Boton, Alerta, Modal } from "../../components/ui";
import { Pill } from "../../components/Pill";
import { DataTable } from "../../components/DataTable";
import { useSoloLectura } from "../../permisos";
import { money, fecha } from "../../components/format";

const MEDIOS = ["EFECTIVO", "TRANSFERENCIA", "DEBITO", "CHEQUE"];

/** Cobro que necesita un importe o una cantidad antes de ejecutarse. */
const PEDIDOS = {
  parcial: { titulo: "Cobro parcial", etiqueta: "Importe a cobrar", boton: "Cobrar" },
  adelantar: { titulo: "Adelantar cuotas", etiqueta: "¿Cuántas cuotas adelantar?", boton: "Adelantar" },
  prepago: { titulo: "Prepago de capital", etiqueta: "Importe del prepago", boton: "Aplicar prepago" },
};

const COLS_CUOTAS = [
  { key: "numero_cuota", label: "#" },
  { key: "fecha_vencimiento", label: "Vto", render: (c) => fecha(c.fecha_vencimiento) },
  { key: "total", label: "Cuota", align: "right", render: (c) => money(c.total) },
  { key: "pagado", label: "Pagado", align: "right", render: (c) => money(c.pagado) },
  { key: "estado", label: "Estado", render: (c) => (
    <Pill tono={c.estado === "PAGADA" ? "ok" : c.estado === "VENCIDA" ? "crit" : "warn"}>{c.estado}</Pill>) },
];

export default function CajaCreditosPage() {
  const soloLectura = useSoloLectura();
  const [contratos, setContratos] = useState([]);
  const [q, setQ] = useState("");
  const [cto, setCto] = useState(null);
  const [medio, setMedio] = useState("EFECTIVO");
  const [recibo, setRecibo] = useState(null);
  const [error, setError] = useState("");
  const [pedido, setPedido] = useState(null);       // cobro que espera un importe/cantidad
  const [valor, setValor] = useState("");
  const [modoPrepago, setModoPrepago] = useState("BAJA_CUOTA");

  const cargar = () => creditos.ctoListar()
    .then((d) => setContratos(d.items || d))
    .catch((e) => setError(e.message));
  useEffect(() => { cargar(); }, []);

  const activos = useMemo(() => {
    const ql = q.toLowerCase();
    return contratos.filter((c) => c.estado === "ACTIVO" && (!ql
      || (c.cliente_nombre || "").toLowerCase().includes(ql)
      || (c.numero_contrato || "").toLowerCase().includes(ql)));
  }, [contratos, q]);

  const proxima = () => cto?.cuotas?.find((x) => x.estado === "PENDIENTE");

  async function abrir(c) {
    setRecibo(null); setError("");
    try { setCto(await creditos.ctoObtener(c.id)); }
    catch (e) { setError(e.message); }
  }

  async function cobrar(tipo, importe = 0, modo, cuotas) {
    if (!cto) return;
    setError("");
    try {
      await creditos.ctoActividadCaja(cto.id, tipo, importe, medio, modo, cuotas);
      const nuevo = await creditos.ctoObtener(cto.id);
      setCto(nuevo);
      const act = [...nuevo.actividades].reverse().find((a) => a.tipo === tipo && a.estado !== "REVERSADA");
      setRecibo({ act, asiento: nuevo.asientos?.[nuevo.asientos.length - 1], cliente: nuevo.cliente_nombre, contrato: nuevo.numero_contrato });
      cargar();
    } catch (e) { setError(e.message); }
  }

  function confirmarPedido() {
    const v = Number(valor);
    if (!v || v <= 0) return;
    if (pedido === "parcial") cobrar("PAYMENT", v);
    else if (pedido === "adelantar") cobrar("PAYMENT", 0, undefined, v);
    else cobrar("PARTIAL_PREPAYMENT", v, modoPrepago);
    setPedido(null); setValor("");
  }

  return (
    <>
      <PageHeader
        titulo="Caja de créditos"
        descripcion="Cobranza de contratos: elegí el contrato y el medio de pago, y cobrá la cuota (total o parcial) o registrá un prepago. Cada cobro se asienta en el Libro Diario."
      />

      {error && <div className="mb-4"><Alerta>{error}</Alerta></div>}

      <div className="grid gap-4 lg:grid-cols-[320px,1fr]">
        <Card padding={false}>
          <div className="p-3 border-b border-gray-200">
            <input className="input w-full" value={q} onChange={(e) => setQ(e.target.value)}
                   placeholder="Buscar contrato o cliente…" aria-label="Buscar contrato o cliente" />
          </div>
          <div className="max-h-[520px] overflow-y-auto divide-y divide-gray-100">
            {activos.map((c) => (
              <button key={c.id} onClick={() => abrir(c)}
                      className={`w-full text-left px-4 py-3 hover:bg-gray-50 ${cto?.id === c.id ? "bg-blue-50" : ""}`}>
                <p className="font-medium text-gray-800 text-sm">{c.numero_contrato}</p>
                <p className="text-sm text-gray-600">{c.cliente_nombre}</p>
                <p className="text-xs text-gray-400">saldo {money(c.saldo_capital)}</p>
              </button>
            ))}
            {!activos.length && <p className="px-4 py-6 text-sm text-gray-400">Sin contratos activos.</p>}
          </div>
        </Card>

        <Card>
          {!cto ? <p className="text-sm text-gray-500">Elegí un contrato para cobrar.</p> : (
            <>
              <h2 className="font-semibold text-gray-800">{cto.numero_contrato} · {cto.cliente_nombre}</h2>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-3">
                {[
                  { label: "Saldo capital", valor: money(cto.saldo_capital) },
                  { label: "Próxima cuota", valor: proxima() ? `#${proxima().numero_cuota} · ${money(proxima().total)}` : "—" },
                  { label: "Vence", valor: proxima() ? fecha(proxima().fecha_vencimiento) : "—" },
                  { label: "Ya pagado (cuota)", valor: money(proxima()?.pagado || 0) },
                ].map((m) => (
                  <div key={m.label} className="border border-gray-200 rounded-lg px-3 py-2">
                    <p className="text-xs text-gray-500">{m.label}</p>
                    <p className="font-semibold text-gray-800 text-sm">{m.valor}</p>
                  </div>
                ))}
              </div>

              <div className="flex flex-wrap items-end gap-3 mt-4">
                <Field label="Medio de pago">
                  <select className="input" value={medio} onChange={(e) => setMedio(e.target.value)}>
                    {MEDIOS.map((m) => <option key={m} value={m}>{m}</option>)}
                  </select>
                </Field>
                {soloLectura ? (
                  <Pill tono="neutral">Sólo lectura</Pill>
                ) : (
                  <>
                    <Boton disabled={!proxima()} onClick={() => cobrar("PAYMENT")}>Cobrar cuota</Boton>
                    <Boton variante="secundario" disabled={!proxima()} onClick={() => { setPedido("parcial"); setValor(""); }}>
                      Cobro parcial
                    </Boton>
                    <Boton variante="secundario" disabled={!proxima()} onClick={() => { setPedido("adelantar"); setValor(""); }}>
                      Adelantar cuotas
                    </Boton>
                    <Boton variante="secundario" onClick={() => { setPedido("prepago"); setValor(""); }}>
                      Prepago capital
                    </Boton>
                  </>
                )}
              </div>

              {recibo && (
                <div className="mt-4 border border-gray-200 rounded-xl overflow-hidden">
                  <p className="px-4 py-2 bg-gray-50 border-b border-gray-200 text-sm font-medium text-gray-700">
                    Recibo — {recibo.contrato}
                  </p>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-3 p-4 text-sm">
                    <div><p className="text-xs text-gray-500">Cliente</p><b>{recibo.cliente}</b></div>
                    <div><p className="text-xs text-gray-500">Operación</p><b>{recibo.act?.tipo}</b></div>
                    <div><p className="text-xs text-gray-500">Importe</p><b>{money(recibo.act?.importe || 0)}</b></div>
                    <div><p className="text-xs text-gray-500">Medio</p><b>{recibo.act?.dato?.medio_pago || medio}</b></div>
                    {recibo.act?.dato?.interes_punitorio > 0 && (
                      <div><p className="text-xs text-gray-500">Mora</p>
                        <b>{money(recibo.act.dato.interes_punitorio + (recibo.act.dato.iva_punitorio || 0))}</b></div>
                    )}
                    <div><p className="text-xs text-gray-500">Fecha</p><b>{fecha(recibo.act?.fecha)}</b></div>
                  </div>
                  {recibo.asiento && (
                    <table className="w-full text-sm border-t border-gray-200">
                      <thead>
                        <tr className="bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
                          <th className="px-4 py-2 text-left">Cuenta</th>
                          <th className="px-4 py-2 text-right">Debe</th>
                          <th className="px-4 py-2 text-right">Haber</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {recibo.asiento.lineas.map((l, i) => (
                          <tr key={i}>
                            <td className="px-4 py-1.5">{l.cuenta}{l.nombre ? ` · ${l.nombre}` : ""}</td>
                            <td className="px-4 py-1.5 text-right tabular-nums">{l.debe ? money(l.debe) : ""}</td>
                            <td className="px-4 py-1.5 text-right tabular-nums">{l.haber ? money(l.haber) : ""}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              )}

              <details className="mt-4">
                <summary className="text-sm text-gray-600 cursor-pointer">Plan de cuotas ({cto.cuotas.length})</summary>
                <div className="mt-2">
                  <DataTable columns={COLS_CUOTAS} rows={cto.cuotas} rowKey={(c) => c.numero_cuota}
                             pageSize={12} emptyText="El contrato no tiene cuotas" />
                </div>
              </details>
            </>
          )}
        </Card>
      </div>

      {pedido && (
        <Modal
          titulo={PEDIDOS[pedido].titulo}
          ancho="max-w-md"
          onClose={() => setPedido(null)}
          footer={
            <>
              <span className="flex-1" />
              <Boton variante="secundario" onClick={() => setPedido(null)}>Cancelar</Boton>
              <Boton disabled={!Number(valor)} onClick={confirmarPedido}>{PEDIDOS[pedido].boton}</Boton>
            </>
          }
        >
          <Field label={PEDIDOS[pedido].etiqueta}>
            <input type="number" className="input w-full" value={valor} autoFocus
                   onChange={(e) => setValor(e.target.value)} />
          </Field>
          {pedido === "prepago" && (
            <div className="mt-3">
              <Field label="¿Cómo aplicar el prepago?">
                <select className="input w-full" value={modoPrepago} onChange={(e) => setModoPrepago(e.target.value)}>
                  <option value="BAJA_CUOTA">Baja de cuota (mismo plazo)</option>
                  <option value="BAJA_PLAZO">Baja de plazo (misma cuota)</option>
                </select>
              </Field>
            </div>
          )}
        </Modal>
      )}
    </>
  );
}
