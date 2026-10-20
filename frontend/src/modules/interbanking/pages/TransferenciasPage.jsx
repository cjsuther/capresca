import { useEffect, useMemo, useState } from "react";
import {
  listarTransferencias,
  crearTransferencia,
  getTransferenciasLocal,
  getCuentas,
} from "../../../api/interbanking";
import { PermissionGate } from "../../../components/PrivateRoute";
import { CheckCircle, Plus, RefreshCw, X } from "lucide-react";

const todayISO = () => new Date().toISOString().slice(0, 10);

const STATUS_COLORS = {
  ACREDITADA: "bg-green-100 text-green-700",
  PROCESANDO: "bg-yellow-100 text-yellow-700",
  PENDING_AUTHORIZATION: "bg-yellow-100 text-yellow-700",
  INICIADA:   "bg-blue-100 text-blue-700",
  RECHAZADA:  "bg-red-100 text-red-600",
  ERROR:      "bg-gray-100 text-gray-600",
};

const fmtMoney = (n, cur = "ARS") =>
  `${cur} ${Number(n ?? 0).toLocaleString("es-AR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

// Interbanking pagina el listado; se traen todas las páginas del rango para que los filtros de
// columna miren todas las transferencias y no sólo la primera página. Tope por si el rango es enorme.
const POR_PAGINA = 500;
const MAX_PAGINAS = 20;

const TAMANIOS = [25, 50, 100];

// Las que Interbanking rechazó no figuran en su listado: salen del registro propio del módulo.
const POR_PAGINA_LOCAL = 100;

const diaArgentina = (iso) =>
  iso ? new Date(iso).toLocaleDateString("en-CA", { timeZone: "America/Argentina/Buenos_Aires" }) : "";

// Una transferencia rechazada con la forma de las del listado de Interbanking.
// `cuenta_origen` se guarda como "banco/número/tipo".
function filaRechazada(t) {
  const [banco, numero, tipo] = (t.cuenta_origen || "").split("/");
  return {
    _local: true,
    _status: t.status,
    _motivo: t.motivo,
    _id: t.id,
    transfer_id: `Intento ${t.id}`,
    request_date: diaArgentina(t.initiated_at),
    debit_account: t.cuenta_origen ? { bank_number: banco, account_number: numero, account_type: tipo } : null,
    credit_account: { account_cbu: t.cbu_destino },
    amount: t.monto,
    currency: t.moneda,
    comments: t.concepto,
    cargado_por: t.cargado_por,
  };
}

const SIN_FILTROS = { fecha: "", id: "", origen: "", destino: "", montoMin: "", montoMax: "", comentario: "", estado: "", motivo: "" };

const norm = (v) => String(v ?? "").toLowerCase();
const textoCuenta = (c) =>
  c ? [c.bank_name, c.account_type, c.account_number, c.account_cbu, c.cbu, c.customer_cuit, c.cuit].join(" ") : "";
const estadoDe = (t) => t._status || t.status || "—";
// Acepta "1500.5" y el formato local "1.500,50".
const numero = (v) => {
  if (v === "") return null;
  const s = String(v).trim();
  const n = Number(s.includes(",") ? s.replace(/\./g, "").replace(",", ".") : s);
  return Number.isNaN(n) ? null : n;
};

function pasaFiltros(t, f) {
  const contiene = (valor, buscado) => !buscado || norm(valor).includes(norm(buscado).trim());
  const min = numero(f.montoMin);
  const max = numero(f.montoMax);
  return (
    contiene(t.request_date, f.fecha) &&
    contiene(`${t.transfer_id} ${t.transaction_number ?? ""} ${t.reference_number ?? ""}`, f.id) &&
    contiene(textoCuenta(t.debit_account), f.origen) &&
    contiene(textoCuenta(t.credit_account), f.destino) &&
    (min == null || Number(t.amount) >= min) &&
    (max == null || Number(t.amount) <= max) &&
    contiene(`${t.transfer_comments ?? t.comments ?? ""} ${t.transfer_type_description ?? ""}`, f.comentario) &&
    (!f.estado || estadoDe(t) === f.estado) &&
    contiene(t._motivo, f.motivo)
  );
}

// FastAPI devuelve `detail` como string en 4xx normales y como array de
// {loc, msg, type, ...} en 422. Convertir a string siempre.
const errMsg = (err, fallback) => {
  const d = err?.response?.data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map(e => `${(e.loc || []).join(".")} - ${e.msg}`).join("; ");
  return fallback;
};

export default function TransferenciasPage() {
  const [filtros, setFiltros] = useState({ date_since: todayISO(), date_until: todayISO() });
  const [data, setData] = useState({ transfers: [], general_data: {}, remotas: 0 });
  const [conError, setConError] = useState(true);
  const [col, setColRaw] = useState(SIN_FILTROS);
  const [pagina, setPagina] = useState(0);
  const [porPagina, setPorPagina] = useState(50);
  // Cambiar un filtro vuelve a la primera página.
  const setCol = (v) => { setColRaw(v); setPagina(0); };
  const [isMock, setIsMock] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [cuentas, setCuentas] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    cuenta_debito_key: "",
    cuenta_debito_account_number: "",
    cuenta_debito_account_type: "",
    cuenta_debito_bank_id: "",
    cbu_destino: "",
    monto: "",
    moneda: "ARS",
    comentario: "",
  });
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(null);

  const rechazadas = async () => {
    const filas = [];
    for (let page = 1; page <= MAX_PAGINAS; page++) {
      const r = await getTransferenciasLocal({
        status: "ERROR", date_since: filtros.date_since, date_until: filtros.date_until,
        page, per_page: POR_PAGINA_LOCAL,
      });
      filas.push(...(r.data || []));
      if (filas.length >= (r.total ?? 0) || !r.data?.length) break;
    }
    return filas.map(filaRechazada);
  };

  const cargar = async (incluirError = conError) => {
    setLoading(true);
    setError("");
    try {
      let result = await listarTransferencias({ ...filtros, page: 0, rows: POR_PAGINA });
      const transfers = [...(result.transfers || [])];
      const total = result.general_data?.total_rows ?? transfers.length;
      for (let page = 1; transfers.length < total && page < MAX_PAGINAS; page++) {
        const sig = await listarTransferencias({ ...filtros, page, rows: POR_PAGINA });
        if (!sig.transfers?.length) break;
        transfers.push(...sig.transfers);
      }
      const remotas = transfers.length;
      if (incluirError) {
        transfers.push(...await rechazadas());
        // Por fecha, las más nuevas primero (el orden es estable: no altera el de Interbanking).
        transfers.sort((a, b) => String(b.request_date ?? "").localeCompare(String(a.request_date ?? "")));
      }
      setData({ transfers, general_data: result.general_data || {}, remotas });
      setPagina(0);
      setIsMock(!!result.mock);
    } catch (err) {
      setError(errMsg(err, "Error al listar transferencias"));
    } finally {
      setLoading(false);
    }
  };

  const cargarCuentas = async () => {
    try {
      const d = await getCuentas();
      const list = d?.accounts ?? (Array.isArray(d) ? d : []);
      setCuentas(list);
    } catch {
      // si falla, el dropdown queda vacío y se puede pegar el CBU a mano
    }
  };

  useEffect(() => {
    cargar();
    cargarCuentas();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const created = await crearTransferencia({
        cuenta_debito_account_number: form.cuenta_debito_account_number,
        cuenta_debito_account_type: form.cuenta_debito_account_type,
        cuenta_debito_bank_id: form.cuenta_debito_bank_id || null,
        cbu_destino: form.cbu_destino,
        monto: parseFloat(form.monto),
        moneda: form.moneda,
        comentario: form.comentario,
      });
      setSuccess(created);
      setShowForm(false);
      setForm({
        cuenta_debito_key: "",
        cuenta_debito_account_number: "",
        cuenta_debito_account_type: "",
        cuenta_debito_bank_id: "",
        cbu_destino: "", monto: "", moneda: "ARS", comentario: "",
      });
      cargar();
    } catch (err) {
      setError(errMsg(err, "Error al crear transferencia"));
    } finally {
      setSubmitting(false);
    }
  };

  // Clave compuesta para identificar cada cuenta del listado (bank_id|account_number|account_type)
  const accountKey = (c) =>
    `${c.bank_id || c.bank_number || ""}|${c.account_number || ""}|${c.account_type || ""}`;
  const cuentaSeleccionada = cuentas.find((c) => accountKey(c) === form.cuenta_debito_key);

  const estados = useMemo(() => [...new Set(data.transfers.map(estadoDe))].sort(), [data.transfers]);
  const visibles = useMemo(() => data.transfers.filter((t) => pasaFiltros(t, col)), [data.transfers, col]);
  const paginas = Math.max(1, Math.ceil(visibles.length / porPagina));
  const paginaActual = Math.min(pagina, paginas - 1);
  const enPagina = visibles.slice(paginaActual * porPagina, (paginaActual + 1) * porPagina);
  const desde = visibles.length ? paginaActual * porPagina + 1 : 0;
  const hasta = Math.min((paginaActual + 1) * porPagina, visibles.length);
  const hayFiltros = Object.values(col).some(Boolean);
  const totalRemoto = data.general_data?.total_rows;
  const errores = data.transfers.length - data.remotas;
  const total = totalRemoto != null ? totalRemoto + errores : null;
  const incompleto = totalRemoto != null && data.remotas < totalRemoto;

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <div className="flex items-center gap-3">
          <h2 className="text-xl font-semibold text-gray-800">Transferencias</h2>
          {isMock && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 border border-amber-200">
              MOCK
            </span>
          )}
        </div>
        <PermissionGate moduleCode="interbanking" action="transferencias:write">
          <button
            onClick={() => setShowForm(true)}
            className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700"
          >
            <Plus size={15} /> Nueva transferencia
          </button>
        </PermissionGate>
      </div>

      {/* Filtros */}
      <div className="bg-surface border rounded-xl p-4 mb-4 flex flex-wrap items-end gap-3">
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Desde</label>
          <input
            type="date"
            className="input text-sm"
            value={filtros.date_since}
            onChange={(e) => setFiltros({ ...filtros, date_since: e.target.value })}
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Hasta</label>
          <input
            type="date"
            className="input text-sm"
            value={filtros.date_until}
            onChange={(e) => setFiltros({ ...filtros, date_until: e.target.value })}
          />
        </div>
        <label className="flex items-center gap-2 text-sm text-gray-700 py-2">
          <input
            type="checkbox"
            checked={conError}
            onChange={(e) => { setConError(e.target.checked); cargar(e.target.checked); }}
          />
          Incluir las que dieron error
        </label>
        <button
          onClick={() => cargar()}
          disabled={loading}
          className="flex items-center gap-2 bg-surface border text-gray-700 px-3 py-2 rounded-lg text-sm hover:bg-gray-50 disabled:opacity-50"
        >
          <RefreshCw size={15} className={loading ? "animate-spin" : ""} />
          Consultar
        </button>
        <div className="ml-auto flex items-center gap-3 text-xs text-gray-400">
          {hayFiltros && (
            <button onClick={() => setCol(SIN_FILTROS)} className="text-blue-600 hover:underline">
              Limpiar filtros
            </button>
          )}
          <span>
            {hayFiltros
              ? `${visibles.length} de ${data.transfers.length} resultados`
              : total != null && `${total} resultados`}
          </span>
        </div>
      </div>

      {incompleto && !loading && (
        <div className="bg-amber-50 border border-amber-200 text-amber-800 rounded-lg px-4 py-2 text-sm mb-4">
          Se cargaron {data.remotas} de {totalRemoto} transferencias: los filtros sólo miran esas.
          Achicá el rango de fechas para verlas todas.
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-2 text-sm mb-4">{error}</div>
      )}

      {success && (
        <div className="bg-green-50 border border-green-200 rounded-xl p-4 mb-4 flex items-center gap-3">
          <CheckCircle size={20} className="text-green-600" />
          <div className="flex-1">
            <p className="text-sm font-medium text-green-800">Transferencia creada</p>
            <p className="text-xs text-green-600">
              ID Operación: {success.id_operacion_ib || success.id} · Estado: {success.status}
            </p>
          </div>
          <button onClick={() => setSuccess(null)} className="text-xs text-green-600 hover:underline">Cerrar</button>
        </div>
      )}

      {/* Listado */}
      <div className="bg-surface border rounded-xl overflow-x-auto">
        <table className="w-full text-sm min-w-[900px]">
          <thead className="bg-gray-50 text-gray-600">
            <tr>
              <th className="text-left px-4 py-3 font-medium">Fecha</th>
              <th className="text-left px-4 py-3 font-medium">ID</th>
              <th className="text-left px-4 py-3 font-medium">Origen</th>
              <th className="text-left px-4 py-3 font-medium">Destino</th>
              <th className="text-right px-4 py-3 font-medium">Monto</th>
              <th className="text-left px-4 py-3 font-medium">Comentario</th>
              <th className="text-left px-4 py-3 font-medium">Estado</th>
            </tr>
            <tr className="bg-surface">
              <th className="px-2 pb-2"><FiltroTexto etiqueta="Fecha" valor={col.fecha} onChange={(v) => setCol({ ...col, fecha: v })} /></th>
              <th className="px-2 pb-2"><FiltroTexto etiqueta="ID" valor={col.id} onChange={(v) => setCol({ ...col, id: v })} /></th>
              <th className="px-2 pb-2"><FiltroTexto etiqueta="Origen" placeholder="Banco, cuenta, CBU, CUIT" valor={col.origen} onChange={(v) => setCol({ ...col, origen: v })} /></th>
              <th className="px-2 pb-2"><FiltroTexto etiqueta="Destino" placeholder="Banco, cuenta, CBU, CUIT" valor={col.destino} onChange={(v) => setCol({ ...col, destino: v })} /></th>
              <th className="px-2 pb-2">
                <div className="flex gap-1">
                  <FiltroTexto etiqueta="Monto desde" placeholder="Desde" valor={col.montoMin} onChange={(v) => setCol({ ...col, montoMin: v })} />
                  <FiltroTexto etiqueta="Monto hasta" placeholder="Hasta" valor={col.montoMax} onChange={(v) => setCol({ ...col, montoMax: v })} />
                </div>
              </th>
              <th className="px-2 pb-2"><FiltroTexto etiqueta="Comentario" placeholder="Texto o tipo" valor={col.comentario} onChange={(v) => setCol({ ...col, comentario: v })} /></th>
              <th className="px-2 pb-2">
                <select aria-label="Filtrar Estado" className="input text-xs w-full font-normal" value={col.estado}
                  onChange={(e) => setCol({ ...col, estado: e.target.value })}>
                  <option value="">Todos</option>
                  {estados.map((e) => <option key={e} value={e}>{e}</option>)}
                </select>
                {conError && (
                  <div className="mt-1">
                    <FiltroTexto etiqueta="Motivo del error" placeholder="Motivo del error" valor={col.motivo}
                      onChange={(v) => setCol({ ...col, motivo: v })} />
                  </div>
                )}
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400">Cargando...</td></tr>
            ) : data.transfers.length === 0 ? (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400">Sin transferencias en el rango</td></tr>
            ) : visibles.length === 0 ? (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400">Ninguna transferencia coincide con los filtros</td></tr>
            ) : enPagina.map((t) => {
              const status = estadoDe(t);
              return (
                <tr key={t._local ? `local-${t._id}` : t.transfer_id} className={t._local ? "bg-red-50/40" : "hover:bg-gray-50"}>
                  <td className="px-4 py-3 text-gray-500 text-xs">{t.request_date}</td>
                  <td className="px-4 py-3 font-mono text-xs">{t.transfer_id}</td>
                  <td className="px-4 py-3"><Cuenta c={t.debit_account} /></td>
                  <td className="px-4 py-3"><Cuenta c={t.credit_account} /></td>
                  <td className="px-4 py-3 text-right font-mono">{fmtMoney(t.amount, t.currency)}</td>
                  <td className="px-4 py-3 text-gray-600">
                    {t.transfer_comments || t.comments || "—"}
                    {t.transfer_type_description && (
                      <div className="text-xs text-gray-400">{t.transfer_type_description}</div>
                    )}
                    {t.cargado_por && <div className="text-xs text-gray-400">Cargó: {t.cargado_por}</div>}
                  </td>
                  <td className="px-4 py-3 max-w-xs">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${t._local ? "bg-red-100 text-red-700" : STATUS_COLORS[status] || "bg-gray-100 text-gray-600"}`}>
                      {status}
                    </span>
                    {t._local && (
                      <div className="text-xs text-red-700 mt-1">
                        {t._motivo || "Interbanking rechazó el envío"}
                        <div className="text-gray-400">No llegó a Interbanking: no figura en su listado.</div>
                      </div>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {visibles.length > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-2 pt-3">
          <div className="flex items-center gap-3 text-xs text-gray-500">
            <span>{`${desde}–${hasta} de ${visibles.length.toLocaleString("es-AR")}`}</span>
            <label className="flex items-center gap-1">
              Por página
              <select aria-label="Filas por página" className="input text-xs py-1" value={porPagina}
                onChange={(e) => { setPorPagina(Number(e.target.value)); setPagina(0); }}>
                {TAMANIOS.map((n) => <option key={n} value={n}>{n}</option>)}
              </select>
            </label>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500">Página {paginaActual + 1} de {paginas}</span>
            <button
              disabled={paginaActual <= 0}
              onClick={() => setPagina(paginaActual - 1)}
              className="px-3 py-1.5 text-sm border rounded-lg text-gray-600 hover:bg-gray-50 disabled:opacity-40 disabled:hover:bg-surface"
            >‹ Anterior</button>
            <button
              disabled={paginaActual >= paginas - 1}
              onClick={() => setPagina(paginaActual + 1)}
              className="px-3 py-1.5 text-sm border rounded-lg text-gray-600 hover:bg-gray-50 disabled:opacity-40 disabled:hover:bg-surface"
            >Siguiente ›</button>
          </div>
        </div>
      )}

      {/* Modal Nueva Transferencia */}
      {showForm && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-surface rounded-2xl p-6 w-full max-w-lg shadow-xl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-gray-800">Nueva Transferencia</h3>
              <button onClick={() => setShowForm(false)} className="text-gray-400 hover:text-gray-600"><X size={18} /></button>
            </div>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Cuenta débito</label>
                <select
                  className="input w-full text-sm"
                  value={form.cuenta_debito_key}
                  onChange={(e) => {
                    const key = e.target.value;
                    const acc = cuentas.find((c) => accountKey(c) === key);
                    setForm({
                      ...form,
                      cuenta_debito_key: key,
                      cuenta_debito_account_number: acc?.account_number || "",
                      cuenta_debito_account_type: acc?.account_type || "",
                      cuenta_debito_bank_id: acc?.bank_id || acc?.bank_number || "",
                      moneda: acc?.currency || form.moneda,
                    });
                  }}
                  required
                >
                  <option value="">Seleccionar cuenta...</option>
                  {cuentas.map((c) => {
                    const k = accountKey(c);
                    return (
                      <option key={k} value={k}>
                        {/* El número va primero: todas las cuentas son del mismo banco y tipo, sólo el número las distingue. */}
                        {c.account_number}{c.account_label ? ` · ${c.account_label}` : ""} · {c.bank_name || c.bank_id || c.bank_number} · {c.account_type} ({c.currency})
                      </option>
                    );
                  })}
                </select>
                {cuentaSeleccionada && (
                  <p className="text-xs text-gray-400 mt-1 font-mono">
                    Cuenta: {cuentaSeleccionada.account_number} · Tipo: {cuentaSeleccionada.account_type}
                    {cuentaSeleccionada.bank_id ? ` · BCRA: ${cuentaSeleccionada.bank_id}` : ""}
                  </p>
                )}
                {cuentas.length === 0 && (
                  <p className="text-xs text-amber-600 mt-1">
                    No hay cuentas cargadas. Andá a Cuentas → Refrescar primero.
                  </p>
                )}
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">CBU destino</label>
                <input
                  type="text"
                  inputMode="numeric"
                  pattern="\d{22}"
                  maxLength={22}
                  className="input w-full text-sm font-mono"
                  placeholder="22 dígitos"
                  value={form.cbu_destino}
                  onChange={(e) => setForm({ ...form, cbu_destino: e.target.value.replace(/\D/g, "") })}
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Monto</label>
                  <input
                    type="number" step="0.01" min="0.01"
                    className="input w-full text-sm"
                    placeholder="0.00"
                    value={form.monto}
                    onChange={(e) => setForm({ ...form, monto: e.target.value })}
                    required
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Moneda</label>
                  <select
                    className="input w-full text-sm"
                    value={form.moneda}
                    onChange={(e) => setForm({ ...form, moneda: e.target.value })}
                  >
                    <option value="ARS">ARS</option>
                    <option value="USD">USD</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Comentario</label>
                <input
                  className="input w-full text-sm"
                  placeholder="Descripción / concepto"
                  value={form.comentario}
                  onChange={(e) => setForm({ ...form, comentario: e.target.value })}
                  maxLength={255}
                  required
                />
              </div>

              <div className="text-xs text-gray-400">
                Fecha de solicitud: <span className="font-mono">{todayISO()}</span>
              </div>

              <div className="flex gap-2 justify-end pt-2">
                <button type="button" onClick={() => setShowForm(false)} className="px-4 py-2 text-sm text-gray-600 border rounded-lg hover:bg-gray-50">
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={
                    submitting
                    || !form.cuenta_debito_account_number
                    || !form.cuenta_debito_account_type
                    || form.cbu_destino.length !== 22
                    || !form.monto
                    || !form.comentario
                  }
                  className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                >
                  {submitting ? "Creando..." : "Crear transferencia"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

// Cuenta de origen o destino de una transferencia: banco, tipo y número, CBU y CUIT del titular.
// Interbanking manda `account_cbu` y `customer_cuit`; se aceptan también `cbu`/`cuit`.
function Cuenta({ c }) {
  if (!c) return <span className="text-gray-400">—</span>;
  const cbu = c.account_cbu || c.cbu;
  const cuit = c.customer_cuit || c.cuit;
  const cuenta = [c.account_type, c.account_number].filter(Boolean).join(" ");
  return (
    <div className="text-xs leading-5">
      <div className="text-gray-800 font-medium">
        {c.bank_name || (c.bank_number ? `Banco ${c.bank_number}` : "—")}
        {cuenta && <span className="text-gray-500 font-normal"> · {cuenta}</span>}
      </div>
      {cbu && <div className="font-mono text-gray-500">CBU {cbu}</div>}
      {cuit && <div className="text-gray-400">CUIT {cuit}</div>}
    </div>
  );
}

function FiltroTexto({ etiqueta, valor, onChange, placeholder = "Buscar" }) {
  return (
    <input
      aria-label={`Filtrar ${etiqueta}`}
      className="input text-xs w-full font-normal"
      placeholder={placeholder}
      value={valor}
      onChange={(e) => onChange(e.target.value)}
    />
  );
}
