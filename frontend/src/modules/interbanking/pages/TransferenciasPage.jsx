import { useEffect, useState } from "react";
import {
  getTransferencias, validarCBU, iniciarTransferencia, getEstadoTransferencia, getCuentas,
} from "../../../api/interbanking";
import { PermissionGate } from "../../../components/PrivateRoute";
import { CheckCircle, RefreshCw, ChevronDown, ChevronUp } from "lucide-react";

const STATUS_COLORS = {
  ACREDITADA: "bg-green-100 text-green-700",
  PROCESANDO: "bg-yellow-100 text-yellow-700",
  INICIADA:   "bg-blue-100 text-blue-700",
  RECHAZADA:  "bg-red-100 text-red-600",
  ERROR:      "bg-gray-100 text-gray-600",
};

export default function TransferenciasPage() {
  const [historial, setHistorial] = useState({ data: [], total: 0 });
  const [cuentas, setCuentas] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Formulario
  const [step, setStep] = useState(1); // 1=validar, 2=datos
  const [cbuInput, setCbuInput] = useState("");
  const [validating, setValidating] = useState(false);
  const [destinatario, setDestinatario] = useState(null);
  const [form, setForm] = useState({ cuenta_origen: "", monto: "", concepto: "" });
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [resultado, setResultado] = useState(null);

  // Detalle expandido
  const [detailId, setDetailId] = useState(null);

  const loadHistorial = () => {
    setLoading(true);
    getTransferencias()
      .then(setHistorial)
      .catch(() => setError("Error al cargar historial"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadHistorial();
    getCuentas()
      .then((d) => setCuentas(Array.isArray(d) ? d : d.cuentas || []))
      .catch(() => {});
  }, []);

  const handleValidar = async (e) => {
    e.preventDefault();
    setValidating(true);
    setError("");
    setDestinatario(null);
    try {
      const data = await validarCBU(cbuInput);
      setDestinatario(data);
      setStep(2);
    } catch (err) {
      setError(err.response?.data?.detail || "CBU/Alias inválido o no encontrado");
    } finally {
      setValidating(false);
    }
  };

  const handleIniciar = async () => {
    setError("");
    try {
      const result = await iniciarTransferencia({
        cuenta_origen: form.cuenta_origen,
        cbu_destino: destinatario?.cbu || cbuInput,
        monto: parseFloat(form.monto),
        concepto: form.concepto,
      });
      setResultado(result);
      setConfirmOpen(false);
      setStep(1);
      setCbuInput("");
      setForm({ cuenta_origen: "", monto: "", concepto: "" });
      loadHistorial();
    } catch (err) {
      setError(err.response?.data?.detail || "Error al iniciar transferencia");
      setConfirmOpen(false);
    }
  };

  const handleRefrescarEstado = async (t) => {
    try {
      await getEstadoTransferencia(t.id_operacion_ib || t.id);
      loadHistorial();
    } catch (err) {
      setError(err.response?.data?.detail || "Error al refrescar estado");
    }
  };

  return (
    <div>
      <h2 className="text-xl font-semibold text-gray-800 mb-6">Transferencias</h2>

      {error && <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-2 text-sm mb-4">{error}</div>}

      {resultado && (
        <div className="bg-green-50 border border-green-200 rounded-xl p-4 mb-4 flex items-center gap-3">
          <CheckCircle size={20} className="text-green-600" />
          <div>
            <p className="text-sm font-medium text-green-800">Transferencia iniciada correctamente</p>
            <p className="text-xs text-green-600">ID Operación: {resultado.id_operacion_ib || resultado.id}</p>
          </div>
          <button onClick={() => setResultado(null)} className="ml-auto text-xs text-green-600 hover:underline">Cerrar</button>
        </div>
      )}

      {/* Formulario nueva transferencia */}
      <PermissionGate moduleCode="interbanking" action="transferencias:write">
        <div className="bg-white border rounded-xl p-5 mb-6">
          <h3 className="font-medium text-gray-700 mb-4">Nueva Transferencia</h3>

          {/* Paso 1 — Validar */}
          <form onSubmit={handleValidar} className="flex gap-3 mb-4">
            <input
              className="input flex-1 text-sm"
              placeholder="CBU o Alias del destinatario"
              value={cbuInput}
              onChange={(e) => { setCbuInput(e.target.value); setStep(1); setDestinatario(null); }}
            />
            <button
              type="submit"
              disabled={validating || !cbuInput}
              className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {validating ? "Validando..." : "Validar"}
            </button>
          </form>

          {destinatario && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-4 text-sm">
              <p className="font-medium text-blue-800">{destinatario.titular || "Titular desconocido"}</p>
              <p className="text-xs text-blue-600">{destinatario.banco} · {destinatario.tipo_cuenta}</p>
            </div>
          )}

          {/* Paso 2 — Datos */}
          {step === 2 && (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Cuenta Origen</label>
                <select className="input w-full text-sm" value={form.cuenta_origen} onChange={(e) => setForm({ ...form, cuenta_origen: e.target.value })} required>
                  <option value="">Seleccionar...</option>
                  {cuentas.map((c) => (
                    <option key={c.id} value={c.id}>{c.denominacion || c.nombre || c.id}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Monto</label>
                <input type="number" step="0.01" min="0.01" className="input w-full text-sm" placeholder="0.00" value={form.monto} onChange={(e) => setForm({ ...form, monto: e.target.value })} required />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Concepto</label>
                <input className="input w-full text-sm" placeholder="Descripción..." value={form.concepto} onChange={(e) => setForm({ ...form, concepto: e.target.value })} required />
              </div>
              <div className="col-span-1 sm:col-span-3 flex justify-end">
                <button
                  onClick={() => setConfirmOpen(true)}
                  disabled={!form.cuenta_origen || !form.monto || !form.concepto}
                  className="px-4 py-2 text-sm bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
                >
                  Iniciar Transferencia
                </button>
              </div>
            </div>
          )}
        </div>
      </PermissionGate>

      {/* Modal confirmación */}
      {confirmOpen && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl p-6 w-full max-w-sm shadow-xl">
            <h3 className="font-semibold text-gray-800 mb-4">Confirmar Transferencia</h3>
            <dl className="space-y-2 text-sm mb-6">
              <div className="flex justify-between"><dt className="text-gray-500">Destinatario</dt><dd>{destinatario?.titular || cbuInput}</dd></div>
              <div className="flex justify-between"><dt className="text-gray-500">Monto</dt><dd className="font-bold">ARS {Number(form.monto).toLocaleString("es-AR", { minimumFractionDigits: 2 })}</dd></div>
              <div className="flex justify-between"><dt className="text-gray-500">Concepto</dt><dd>{form.concepto}</dd></div>
            </dl>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setConfirmOpen(false)} className="px-4 py-2 text-sm text-gray-600 border rounded-lg hover:bg-gray-50">Cancelar</button>
              <button onClick={handleIniciar} className="px-4 py-2 text-sm bg-green-600 text-white rounded-lg hover:bg-green-700">Confirmar</button>
            </div>
          </div>
        </div>
      )}

      {/* Historial */}
      <div className="bg-white border rounded-xl overflow-x-auto">
        <div className="flex items-center justify-between px-4 py-3 border-b">
          <h3 className="font-medium text-gray-700">Historial</h3>
          <button onClick={loadHistorial} className="text-xs text-blue-600 hover:underline">Actualizar</button>
        </div>
        <table className="w-full text-sm min-w-[700px]">
          <thead className="bg-gray-50 text-gray-600">
            <tr>
              <th className="text-left px-4 py-3 font-medium">Fecha</th>
              <th className="text-left px-4 py-3 font-medium">ID Operación</th>
              <th className="text-left px-4 py-3 font-medium">CBU Destino</th>
              <th className="text-right px-4 py-3 font-medium">Monto</th>
              <th className="text-left px-4 py-3 font-medium">Concepto</th>
              <th className="text-left px-4 py-3 font-medium">Estado</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400">Cargando...</td></tr>
            ) : historial.data.length === 0 ? (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400">Sin transferencias</td></tr>
            ) : historial.data.map((t) => (
              <>
                <tr key={t.id} className="hover:bg-gray-50 cursor-pointer" onClick={() => setDetailId(detailId === t.id ? null : t.id)}>
                  <td className="px-4 py-3 text-gray-500 text-xs">{t.initiated_at ? new Date(t.initiated_at).toLocaleString() : "—"}</td>
                  <td className="px-4 py-3 font-mono text-xs">{t.id_operacion_ib || t.id}</td>
                  <td className="px-4 py-3 font-mono text-xs">{t.cbu_destino || "—"}</td>
                  <td className="px-4 py-3 text-right font-medium">{t.monto ? `$${Number(t.monto).toLocaleString("es-AR", { minimumFractionDigits: 2 })}` : "—"}</td>
                  <td className="px-4 py-3 text-gray-600">{t.concepto || "—"}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${STATUS_COLORS[t.status] || "bg-gray-100 text-gray-600"}`}>{t.status || "—"}</span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1">
                      {t.status === "PROCESANDO" && (
                        <button
                          onClick={(e) => { e.stopPropagation(); handleRefrescarEstado(t); }}
                          className="p-1 text-gray-400 hover:text-blue-600"
                          title="Refrescar estado"
                        >
                          <RefreshCw size={13} />
                        </button>
                      )}
                      {detailId === t.id ? <ChevronUp size={14} className="text-gray-400" /> : <ChevronDown size={14} className="text-gray-400" />}
                    </div>
                  </td>
                </tr>
                {detailId === t.id && t.last_status_payload && (
                  <tr key={`${t.id}-detail`}>
                    <td colSpan={7} className="px-4 pb-4 bg-gray-50 border-b">
                      <pre className="text-xs text-gray-600 bg-white border rounded-lg p-3 overflow-auto max-h-40 mt-2">
                        {JSON.stringify(t.last_status_payload, null, 2)}
                      </pre>
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
