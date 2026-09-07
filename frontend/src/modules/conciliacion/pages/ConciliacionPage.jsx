import { useState, useEffect } from "react";
import { X, Trash2, Download, ChevronDown } from "lucide-react";
import {
  getConciliacion,
  getSummary,
  getAgencies,
  updateRecord,
  assignAgency,
  removeLink,
  downloadBoleta,
  addAdjustment,
} from "../../../api/conciliacion";
import { PermissionGate } from "../../../components/PrivateRoute";

const fmt = (n) =>
  n != null
    ? `$ ${Number(n).toLocaleString("es-AR", { minimumFractionDigits: 2 })}`
    : "—";

function StatusBadge({ status }) {
  const styles = {
    A_VERIFICAR: "bg-yellow-100 text-yellow-700",
    CONSOLIDADO: "bg-green-100 text-green-700",
    CONSOLIDADO_MANUAL: "bg-blue-100 text-blue-700",
  };
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${styles[status] || "bg-gray-100 text-gray-600"}`}>
      {status}
    </span>
  );
}

function TypeBadge({ type }) {
  const styles = {
    transfer: "bg-blue-100 text-blue-700",
    batch_item: "bg-purple-100 text-purple-700",
  };
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${styles[type] || "bg-gray-100 text-gray-600"}`}>
      {type}
    </span>
  );
}

function MatchTypeBadge({ matchType }) {
  if (!matchType) return null;
  return (
    <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-gray-100 text-gray-600">
      {matchType}
    </span>
  );
}

function LiqBadge() {
  return (
    <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-orange-100 text-orange-700" title="Datos cargados desde Liquidaciones">
      LIQ
    </span>
  );
}

export default function ConciliacionPage() {
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [records, setRecords] = useState([]);
  const [ibTransactions, setIbTransactions] = useState([]);
  const [summary, setSummary] = useState(null);
  const [agencies, setAgencies] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedRecord, setSelectedRecord] = useState(null);
  const [selectedTx, setSelectedTx] = useState(null);
  const [error, setError] = useState("");

  // Edit record form state
  const [editImporteAdeudado, setEditImporteAdeudado] = useState("");
  const [editImportePremios, setEditImportePremios] = useState("");
  const [editLoading, setEditLoading] = useState(false);
  const [editError, setEditError] = useState("");
  const [adjAmount, setAdjAmount] = useState("");
  const [adjReason, setAdjReason] = useState("");
  const [adjLoading, setAdjLoading] = useState(false);
  const [adjError, setAdjError] = useState("");
  const [boletaLoading, setBoletaLoading] = useState(false);
  const [boletaError, setBoletaError] = useState("");

  // Assign agency form state
  const [selectedAgencyId, setSelectedAgencyId] = useState("");
  const [assignLoading, setAssignLoading] = useState(false);
  const [assignSuccess, setAssignSuccess] = useState("");
  const [assignError, setAssignError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [data, summ, agList] = await Promise.all([
        getConciliacion(date),
        getSummary(date),
        getAgencies(),
      ]);
      setRecords(data.reconciliation_records);
      setIbTransactions(data.interbanking_transactions);
      setSummary(summ);
      setAgencies(agList);
    } catch (e) {
      setError(e.response?.data?.detail || "Error al cargar datos");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // Recarga automática al cambiar la fecha
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [date]);

  const handleSelectRecord = (rec) => {
    setSelectedRecord(rec);
    setSelectedTx(null);
    setEditImporteAdeudado(rec.importe_adeudado ?? "");
    setEditImportePremios(rec.importe_premios ?? "");
    setEditError("");
    setAssignSuccess("");
    setAssignError("");
  };

  const handleSelectTx = (tx) => {
    setSelectedTx(tx);
    setSelectedRecord(null);
    setSelectedAgencyId("");
    setAssignSuccess("");
    setAssignError("");
    setEditError("");
  };

  const handleClosePanel = () => {
    setSelectedRecord(null);
    setSelectedTx(null);
  };

  const handleUpdateRecord = async () => {
    if (!selectedRecord) return;
    setEditLoading(true);
    setEditError("");
    try {
      await updateRecord(selectedRecord.id, {
        importe_adeudado: Number(editImporteAdeudado),
        importe_premios: Number(editImportePremios),
      });
      await load();
      // Re-select updated record from refreshed data
      setSelectedRecord(null);
    } catch (e) {
      setEditError(e.response?.data?.detail || "Error al actualizar");
    } finally {
      setEditLoading(false);
    }
  };

  const handleAddAdjustment = async () => {
    if (!selectedRecord) return;
    if (!adjReason.trim()) { setAdjError("Ingresá una justificación"); return; }
    if (adjAmount === "" || isNaN(Number(adjAmount))) { setAdjError("Ingresá un importe válido"); return; }
    setAdjLoading(true);
    setAdjError("");
    try {
      await addAdjustment(selectedRecord.id, Number(adjAmount), adjReason.trim());
      setAdjAmount("");
      setAdjReason("");
      await load();
      setSelectedRecord(null);
    } catch (e) {
      setAdjError(e.response?.data?.detail || "Error al cargar el ajuste");
    } finally {
      setAdjLoading(false);
    }
  };

  const handleDownloadBoleta = async () => {
    if (!selectedRecord) return;
    setBoletaLoading(true);
    setBoletaError("");
    try {
      await downloadBoleta(selectedRecord.id);
    } catch (e) {
      setBoletaError(e.response?.data?.detail || "No se pudo descargar la boleta");
    } finally {
      setBoletaLoading(false);
    }
  };

  const handleRemoveLink = async (linkId) => {
    try {
      await removeLink(linkId);
      await load();
    } catch (e) {
      setEditError(e.response?.data?.detail || "Error al eliminar vínculo");
    }
  };

  const handleAssignAgency = async () => {
    if (!selectedTx || !selectedAgencyId) return;
    setAssignLoading(true);
    setAssignSuccess("");
    setAssignError("");
    try {
      const agency = agencies.find((a) => String(a.client_id) === String(selectedAgencyId));
      await assignAgency(selectedTx.type, selectedTx.id, agency.client_id);
      await load();
      setAssignSuccess("Agencia asignada correctamente");
    } catch (e) {
      setAssignError(e.response?.data?.detail || "Error al asignar agencia");
    } finally {
      setAssignLoading(false);
    }
  };

  const isPanelOpen = selectedRecord !== null || selectedTx !== null;

  return (
    <div className="flex gap-0 relative">
      {/* Main content */}
      <div className={`flex-1 min-w-0 transition-all ${isPanelOpen ? "pr-0" : ""}`}>
        {/* Header */}
        <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
          <h2 className="text-xl font-semibold text-gray-800">Conciliación</h2>
          <div className="flex items-center gap-3">
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              onClick={load}
              disabled={loading}
              className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? "Cargando..." : "Cargar"}
            </button>
          </div>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-2 text-sm mb-4">
            {error}
          </div>
        )}

        {/* Summary bar */}
        {summary && (
          <div className="bg-white border rounded-xl p-4 mb-5 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4 text-sm">
            <div>
              <p className="text-xs text-gray-500 mb-1">A Verificar</p>
              <p className="font-semibold text-yellow-700">{summary.A_VERIFICAR ?? 0}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500 mb-1">Consolidado</p>
              <p className="font-semibold text-green-700">{summary.CONSOLIDADO ?? 0}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500 mb-1">Consolidado Manual</p>
              <p className="font-semibold text-blue-700">{summary.CONSOLIDADO_MANUAL ?? 0}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500 mb-1">Total Adeudado</p>
              <p className="font-semibold text-gray-800">{fmt(summary.total_importe_adeudado)}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500 mb-1">Total Neto</p>
              <p className="font-semibold text-gray-800">{fmt(summary.total_importe_neto)}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500 mb-1">Total Depositado</p>
              <p className="font-semibold text-gray-800">{fmt(summary.total_importe_depositado)}</p>
            </div>
          </div>
        )}

        {/* Grids */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          {/* Records grid */}
          <div className="bg-white border rounded-xl overflow-hidden">
            <div className="px-4 py-3 border-b bg-gray-50">
              <h3 className="text-sm font-semibold text-gray-700">Registros de Conciliación</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm min-w-[600px]">
                <thead className="bg-gray-50 text-gray-600">
                  <tr>
                    <th className="text-left px-3 py-2 font-medium">Agencia</th>
                    <th className="text-left px-3 py-2 font-medium">Nro</th>
                    <th className="text-right px-3 py-2 font-medium">Adeudado</th>
                    <th className="text-right px-3 py-2 font-medium">Premios</th>
                    <th className="text-right px-3 py-2 font-medium">Depositado</th>
                    <th className="text-right px-3 py-2 font-medium">Neto</th>
                    <th className="text-left px-3 py-2 font-medium">Estado</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {records.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="px-4 py-8 text-center text-gray-400 text-sm">
                        Sin registros
                      </td>
                    </tr>
                  ) : (
                    records.map((rec) => (
                      <tr
                        key={rec.id}
                        onClick={() => handleSelectRecord(rec)}
                        className={`hover:bg-gray-50 cursor-pointer ${selectedRecord?.id === rec.id ? "bg-blue-50" : ""}`}
                      >
                        <td className="px-3 py-2 truncate max-w-[120px]" title={rec.agency_legal_name}>
                          {rec.agency_legal_name || "—"}
                        </td>
                        <td className="px-3 py-2 text-gray-500">{rec.agency_number || "—"}</td>
                        <td className="px-3 py-2 text-right font-mono text-xs">{fmt(rec.importe_adeudado)}</td>
                        <td className="px-3 py-2 text-right font-mono text-xs">{fmt(rec.importe_premios)}</td>
                        <td className="px-3 py-2 text-right font-mono text-xs">{fmt(rec.importe_depositado)}</td>
                        <td className={`px-3 py-2 text-right font-mono text-xs font-semibold ${rec.importe_neto != null && Number(rec.importe_neto) <= 0 ? "text-green-600" : "text-red-600"}`}>
                          {fmt(rec.importe_neto)}
                        </td>
                        <td className="px-3 py-2 space-x-1">
                          <StatusBadge status={rec.status} />
                          {rec.has_liquidacion && <LiqBadge />}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* IB Transactions grid */}
          <div className="bg-white border rounded-xl overflow-hidden">
            <div className="px-4 py-3 border-b bg-gray-50">
              <h3 className="text-sm font-semibold text-gray-700">Transacciones Interbanking</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm min-w-[560px]">
                <thead className="bg-gray-50 text-gray-600">
                  <tr>
                    <th className="text-left px-3 py-2 font-medium">Tipo</th>
                    <th className="text-left px-3 py-2 font-medium">ID</th>
                    <th className="text-left px-3 py-2 font-medium">CBU</th>
                    <th className="text-right px-3 py-2 font-medium">Importe</th>
                    <th className="text-left px-3 py-2 font-medium">Concepto</th>
                    <th className="text-left px-3 py-2 font-medium">Agencia</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {ibTransactions.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-4 py-8 text-center text-gray-400 text-sm">
                        Sin transacciones
                      </td>
                    </tr>
                  ) : (
                    ibTransactions.map((tx) => (
                      <tr
                        key={`${tx.type}-${tx.id}`}
                        onClick={() => handleSelectTx(tx)}
                        className={`hover:bg-gray-50 cursor-pointer ${selectedTx?.id === tx.id && selectedTx?.type === tx.type ? "bg-blue-50" : ""}`}
                      >
                        <td className="px-3 py-2">
                          <TypeBadge type={tx.type} />
                        </td>
                        <td className="px-3 py-2 font-mono text-xs text-gray-600">{tx.id}</td>
                        <td className="px-3 py-2 font-mono text-xs text-gray-600">
                          {tx.cbu ? `${String(tx.cbu).slice(0, 10)}...` : "—"}
                        </td>
                        <td className="px-3 py-2 text-right font-mono text-xs">{fmt(tx.amount)}</td>
                        <td className="px-3 py-2 text-gray-500 truncate max-w-[100px]" title={tx.concepto}>
                          {tx.concepto ? `${String(tx.concepto).slice(0, 20)}${String(tx.concepto).length > 20 ? "..." : ""}` : "—"}
                        </td>
                        <td className="px-3 py-2">
                          {tx.resolved_legal_name ? (
                            <span className="text-xs text-gray-700">{tx.resolved_legal_name}</span>
                          ) : (
                            <span className="text-xs text-gray-400 italic">Sin asignar</span>
                          )}
                          {tx.match_type && (
                            <span className="ml-1">
                              <MatchTypeBadge matchType={tx.match_type} />
                            </span>
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      {/* Side panel */}
      {isPanelOpen && (
        <div className="w-80 flex-shrink-0 bg-white border-l shadow-lg ml-5 rounded-xl overflow-y-auto max-h-[calc(100vh-120px)] sticky top-4 self-start">
          <div className="flex items-center justify-between px-4 py-3 border-b bg-gray-50">
            <h3 className="text-sm font-semibold text-gray-700">
              {selectedRecord ? "Detalle Registro" : "Detalle Transacción"}
            </h3>
            <button
              onClick={handleClosePanel}
              className="text-gray-400 hover:text-gray-600 p-1 rounded"
            >
              <X size={16} />
            </button>
          </div>

          {/* Record detail panel */}
          {selectedRecord && (
            <div className="p-4 space-y-4">
              <div className="space-y-1.5">
                <p className="text-xs text-gray-500">Agencia</p>
                <p className="text-sm font-medium text-gray-800">{selectedRecord.agency_legal_name || "—"}</p>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <p className="text-xs text-gray-500">Número</p>
                  <p className="text-sm">{selectedRecord.agency_number || "—"}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">CUIT/RUT</p>
                  <p className="text-sm font-mono">{selectedRecord.tax_id || "—"}</p>
                </div>
              </div>
              <div>
                <p className="text-xs text-gray-500 mb-1">Estado</p>
                <div className="flex items-center gap-2">
                  <StatusBadge status={selectedRecord.status} />
                  {selectedRecord.has_liquidacion && <LiqBadge />}
                </div>
              </div>
              {selectedRecord.has_liquidacion && (
                <div className="bg-orange-50 border border-orange-200 rounded-lg px-3 py-2">
                  <p className="text-xs text-orange-700">
                    Importes adeudado y premios cargados automáticamente desde el módulo de Liquidaciones.
                  </p>
                </div>
              )}
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <p className="text-xs text-gray-500">Adeudado</p>
                  <p className="font-mono text-xs">{fmt(selectedRecord.importe_adeudado)}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Premios</p>
                  <p className="font-mono text-xs">{fmt(selectedRecord.importe_premios)}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Depositado</p>
                  <p className="font-mono text-xs">{fmt(selectedRecord.importe_depositado)}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Neto</p>
                  <p className={`font-mono text-xs font-semibold ${selectedRecord.importe_neto != null && Number(selectedRecord.importe_neto) <= 0 ? "text-green-600" : "text-red-600"}`}>
                    {fmt(selectedRecord.importe_neto)}
                  </p>
                </div>
              </div>

              {/* Edit form */}
              <PermissionGate moduleCode="conciliacion" action="write">
                <div className="border rounded-lg p-3 space-y-3 bg-gray-50">
                  <p className="text-xs font-semibold text-gray-700">Editar importes</p>
                  <div>
                    <label className="text-xs text-gray-500 block mb-1">Importe Adeudado</label>
                    <input
                      type="number"
                      step="0.01"
                      value={editImporteAdeudado}
                      onChange={(e) => setEditImporteAdeudado(e.target.value)}
                      className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-gray-500 block mb-1">Importe Premios</label>
                    <input
                      type="number"
                      step="0.01"
                      value={editImportePremios}
                      onChange={(e) => setEditImportePremios(e.target.value)}
                      className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                  {editError && (
                    <p className="text-xs text-red-600">{editError}</p>
                  )}
                  <button
                    onClick={handleUpdateRecord}
                    disabled={editLoading}
                    className="w-full px-3 py-1.5 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                  >
                    {editLoading ? "Guardando..." : "Guardar"}
                  </button>
                </div>
              </PermissionGate>

              {/* Ajuste manual */}
              <PermissionGate moduleCode="conciliacion" action="write">
                <div className="border rounded-lg p-3 space-y-3 bg-amber-50">
                  <p className="text-xs font-semibold text-gray-700">Ajuste manual</p>
                  <p className="text-[11px] text-gray-500 -mt-1">
                    Importe con signo: positivo acredita a la agencia, negativo reduce. Queda registrado con tu usuario, fecha y hora.
                  </p>
                  <div>
                    <label className="text-xs text-gray-500 block mb-1">Importe del ajuste</label>
                    <input
                      type="number"
                      step="0.01"
                      value={adjAmount}
                      onChange={(e) => setAdjAmount(e.target.value)}
                      className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-gray-500 block mb-1">Justificación</label>
                    <textarea
                      rows={2}
                      value={adjReason}
                      onChange={(e) => setAdjReason(e.target.value)}
                      placeholder="Motivo del ajuste"
                      className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
                    />
                  </div>
                  {adjError && <p className="text-xs text-red-600">{adjError}</p>}
                  <button
                    onClick={handleAddAdjustment}
                    disabled={adjLoading}
                    className="w-full px-3 py-1.5 text-sm bg-amber-600 text-white rounded-lg hover:bg-amber-700 disabled:opacity-50"
                  >
                    {adjLoading ? "Cargando..." : "Cargar ajuste"}
                  </button>
                </div>
              </PermissionGate>

              {/* Linked IB transactions */}
              {selectedRecord.links && selectedRecord.links.length > 0 && (
                <div className="space-y-2">
                  <p className="text-xs font-semibold text-gray-700">Transacciones vinculadas</p>
                  {selectedRecord.links.map((link) => (
                    <div key={link.id} className="flex items-center justify-between border rounded-lg px-3 py-2 text-xs bg-white">
                      <div>
                        <span className="font-mono text-gray-600">{link.ib_transaction_id}</span>
                        <span className="ml-1 text-gray-400">({link.ib_transaction_type})</span>
                        {link.ib_amount != null && (
                          <span className="ml-2 text-gray-500">{fmt(link.ib_amount)}</span>
                        )}
                      </div>
                      <PermissionGate moduleCode="conciliacion" action="write">
                        <button
                          onClick={() => handleRemoveLink(link.id)}
                          className="text-red-400 hover:text-red-600 p-0.5 rounded"
                          title="Eliminar vínculo"
                        >
                          <Trash2 size={13} />
                        </button>
                      </PermissionGate>
                    </div>
                  ))}
                </div>
              )}

              {/* Download boleta */}
              {selectedRecord.status !== "A_VERIFICAR" && (
                <div>
                  <button
                    type="button"
                    onClick={handleDownloadBoleta}
                    disabled={boletaLoading}
                    className="flex items-center justify-center gap-2 w-full px-3 py-1.5 text-sm border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 disabled:opacity-50"
                  >
                    <Download size={14} />
                    {boletaLoading ? "Descargando..." : "Descargar Boleta"}
                  </button>
                  {boletaError && <p className="text-xs text-red-600 mt-1">{boletaError}</p>}
                </div>
              )}
            </div>
          )}

          {/* IB Transaction detail panel */}
          {selectedTx && (
            <div className="p-4 space-y-4">
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <p className="text-xs text-gray-500">Tipo</p>
                  <TypeBadge type={selectedTx.type} />
                </div>
                <div>
                  <p className="text-xs text-gray-500">ID</p>
                  <p className="font-mono text-xs">{selectedTx.id}</p>
                </div>
              </div>
              {selectedTx.date && (
                <div>
                  <p className="text-xs text-gray-500">Fecha</p>
                  <p className="text-sm">{selectedTx.date}</p>
                </div>
              )}
              <div>
                <p className="text-xs text-gray-500">CBU</p>
                <p className="font-mono text-xs break-all">{selectedTx.cbu || "—"}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Importe</p>
                <p className="font-mono text-sm font-semibold">{fmt(selectedTx.amount)}</p>
              </div>
              {selectedTx.concepto && (
                <div>
                  <p className="text-xs text-gray-500">Concepto</p>
                  <p className="text-sm text-gray-700 break-words">{selectedTx.concepto}</p>
                </div>
              )}
              <div>
                <p className="text-xs text-gray-500">Asignación actual</p>
                {selectedTx.resolved_legal_name ? (
                  <p className="text-sm font-medium text-gray-800">{selectedTx.resolved_legal_name}</p>
                ) : (
                  <p className="text-sm text-gray-400 italic">Sin asignar</p>
                )}
              </div>

              {/* Assign agency */}
              <PermissionGate moduleCode="conciliacion" action="write">
                <div className="border rounded-lg p-3 space-y-3 bg-gray-50">
                  <p className="text-xs font-semibold text-gray-700">Asignar Agencia</p>
                  <div className="relative">
                    <select
                      value={selectedAgencyId}
                      onChange={(e) => setSelectedAgencyId(e.target.value)}
                      className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm appearance-none focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white pr-7"
                    >
                      <option value="">Seleccionar agencia...</option>
                      {agencies.map((ag) => (
                        <option key={ag.client_id} value={ag.client_id}>
                          {ag.agency_number} - {ag.legal_name}
                        </option>
                      ))}
                    </select>
                    <ChevronDown size={14} className="absolute right-2 top-2.5 text-gray-400 pointer-events-none" />
                  </div>
                  {assignSuccess && (
                    <p className="text-xs text-green-600">{assignSuccess}</p>
                  )}
                  {assignError && (
                    <p className="text-xs text-red-600">{assignError}</p>
                  )}
                  <button
                    onClick={handleAssignAgency}
                    disabled={assignLoading || !selectedAgencyId}
                    className="w-full px-3 py-1.5 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                  >
                    {assignLoading ? "Asignando..." : "Confirmar"}
                  </button>
                </div>
              </PermissionGate>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
