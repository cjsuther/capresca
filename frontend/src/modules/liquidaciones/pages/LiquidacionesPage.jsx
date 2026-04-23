import { useState, useEffect, useRef } from "react";
import { X, Upload, FolderOpen, Download, CheckCircle, XCircle, RefreshCw } from "lucide-react";
import {
  getBatches,
  getBatchDetalle,
  getBatchValidaciones,
  getBatchArchivos,
  processZip,
  uploadZip,
  retryConciliacion,
  getArchivoUrl,
} from "../../../api/liquidaciones";
import { PermissionGate } from "../../../components/PrivateRoute";

const fmt = (n) =>
  n != null
    ? `$ ${Number(n).toLocaleString("es-AR", { minimumFractionDigits: 2 })}`
    : "—";

function StatusBadge({ status }) {
  const styles = {
    PENDIENTE: "bg-gray-100 text-gray-600",
    PROCESANDO: "bg-blue-100 text-blue-700",
    VALIDADO: "bg-green-100 text-green-700",
    ERROR: "bg-red-100 text-red-700",
    ENVIADO_CONCILIACION: "bg-purple-100 text-purple-700",
  };
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium whitespace-nowrap ${styles[status] || "bg-gray-100 text-gray-600"}`}>
      {status === "ENVIADO_CONCILIACION" ? "ENVIADO" : status}
    </span>
  );
}

export default function LiquidacionesPage() {
  const [batches, setBatches] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Process modal
  const [showModal, setShowModal] = useState(false);
  const [processMode, setProcessMode] = useState("upload"); // "upload" | "path"
  const [zipPath, setZipPath] = useState("");
  const [processLoading, setProcessLoading] = useState(false);
  const [processError, setProcessError] = useState("");
  const fileInputRef = useRef(null);

  // Selected batch detail
  const [selectedBatch, setSelectedBatch] = useState(null);
  const [detalle, setDetalle] = useState([]);
  const [validaciones, setValidaciones] = useState([]);
  const [archivos, setArchivos] = useState([]);
  const [detailLoading, setDetailLoading] = useState(false);

  // Retry
  const [retryLoading, setRetryLoading] = useState(false);

  const loadBatches = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await getBatches({});
      setBatches(data);
    } catch (e) {
      setError(e.response?.data?.detail || "Error al cargar lotes");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadBatches();
  }, []);

  const handleSelectBatch = async (batch) => {
    setSelectedBatch(batch);
    setDetailLoading(true);
    try {
      const [det, val, arch] = await Promise.all([
        getBatchDetalle(batch.id),
        getBatchValidaciones(batch.id),
        getBatchArchivos(batch.id),
      ]);
      setDetalle(det);
      setValidaciones(val);
      setArchivos(arch);
    } catch (e) {
      // silently fail detail loading
    } finally {
      setDetailLoading(false);
    }
  };

  const handleClosePanel = () => {
    setSelectedBatch(null);
    setDetalle([]);
    setValidaciones([]);
    setArchivos([]);
  };

  const handleProcessPath = async () => {
    if (!zipPath.trim()) return;
    setProcessLoading(true);
    setProcessError("");
    try {
      await processZip(zipPath.trim());
      setShowModal(false);
      setZipPath("");
      await loadBatches();
    } catch (e) {
      setProcessError(e.response?.data?.detail || "Error al procesar archivo");
    } finally {
      setProcessLoading(false);
    }
  };

  const handleProcessUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setProcessLoading(true);
    setProcessError("");
    try {
      await uploadZip(file);
      setShowModal(false);
      await loadBatches();
    } catch (e) {
      setProcessError(e.response?.data?.detail || "Error al subir archivo");
    } finally {
      setProcessLoading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleRetry = async () => {
    if (!selectedBatch) return;
    setRetryLoading(true);
    try {
      await retryConciliacion(selectedBatch.id);
      await loadBatches();
      handleClosePanel();
    } catch (e) {
      setError(e.response?.data?.detail || "Error al reenviar");
    } finally {
      setRetryLoading(false);
    }
  };

  // Aggregate detalle by agency for the summary view
  const agencySummary = detalle.reduce((acc, d) => {
    const key = d.n_agen;
    if (!acc[key]) {
      acc[key] = { n_agen: key, recaudacion: 0, premios: 0, comision: 0, total: 0, count: 0 };
    }
    acc[key].recaudacion += Number(d.recaudacion || 0);
    acc[key].premios += Number(d.premios || 0);
    acc[key].comision += Number(d.comision || 0);
    acc[key].total += Number(d.total || 0);
    acc[key].count += 1;
    return acc;
  }, {});
  const agencyList = Object.values(agencySummary).sort((a, b) => a.n_agen.localeCompare(b.n_agen));

  const isPanelOpen = selectedBatch !== null;

  return (
    <div className="flex gap-0 relative">
      {/* Main content */}
      <div className={`flex-1 min-w-0 transition-all ${isPanelOpen ? "pr-0" : ""}`}>
        {/* Header */}
        <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
          <h2 className="text-xl font-semibold text-gray-800">Liquidaciones</h2>
          <div className="flex items-center gap-3">
            <button
              onClick={loadBatches}
              disabled={loading}
              className="px-3 py-1.5 text-sm border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 disabled:opacity-50"
            >
              {loading ? "Cargando..." : "Actualizar"}
            </button>
            <PermissionGate moduleCode="liquidaciones" action="liq:write">
              <button
                onClick={() => { setShowModal(true); setProcessError(""); }}
                className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700"
              >
                Procesar ZIP
              </button>
            </PermissionGate>
          </div>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-2 text-sm mb-4">
            {error}
          </div>
        )}

        {/* Summary stats */}
        {batches.length > 0 && (
          <div className="bg-white border rounded-xl p-4 mb-5 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4 text-sm">
            <div>
              <p className="text-xs text-gray-500 mb-1">Total Lotes</p>
              <p className="font-semibold text-gray-800">{batches.length}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500 mb-1">Validados</p>
              <p className="font-semibold text-green-700">
                {batches.filter((b) => b.status === "VALIDADO").length}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500 mb-1">Enviados</p>
              <p className="font-semibold text-purple-700">
                {batches.filter((b) => b.status === "ENVIADO_CONCILIACION").length}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500 mb-1">Con Error</p>
              <p className="font-semibold text-red-700">
                {batches.filter((b) => b.status === "ERROR").length}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500 mb-1">Procesando</p>
              <p className="font-semibold text-blue-700">
                {batches.filter((b) => b.status === "PROCESANDO").length}
              </p>
            </div>
          </div>
        )}

        {/* Batches table */}
        <div className="bg-white border rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b bg-gray-50">
            <h3 className="text-sm font-semibold text-gray-700">Lotes Procesados</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[700px]">
              <thead className="bg-gray-50 text-gray-600">
                <tr>
                  <th className="text-left px-3 py-2 font-medium">ID</th>
                  <th className="text-left px-3 py-2 font-medium">Archivo</th>
                  <th className="text-left px-3 py-2 font-medium">Fecha Op.</th>
                  <th className="text-left px-3 py-2 font-medium">Resumen</th>
                  <th className="text-right px-3 py-2 font-medium">Registros</th>
                  <th className="text-right px-3 py-2 font-medium">Agencias</th>
                  <th className="text-left px-3 py-2 font-medium">Estado</th>
                  <th className="text-left px-3 py-2 font-medium">Fecha Proc.</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {batches.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="px-4 py-8 text-center text-gray-400 text-sm">
                      Sin lotes procesados
                    </td>
                  </tr>
                ) : (
                  batches.map((batch) => (
                    <tr
                      key={batch.id}
                      onClick={() => handleSelectBatch(batch)}
                      className={`hover:bg-gray-50 cursor-pointer ${selectedBatch?.id === batch.id ? "bg-blue-50" : ""}`}
                    >
                      <td className="px-3 py-2 font-mono text-xs text-gray-600">{batch.id}</td>
                      <td className="px-3 py-2 truncate max-w-[150px]" title={batch.zip_filename}>
                        {batch.zip_filename}
                      </td>
                      <td className="px-3 py-2 text-gray-600">{batch.operation_date || "—"}</td>
                      <td className="px-3 py-2 font-mono text-xs text-gray-500">{batch.resumen_number || "—"}</td>
                      <td className="px-3 py-2 text-right text-gray-600">{batch.total_detail_records ?? "—"}</td>
                      <td className="px-3 py-2 text-right text-gray-600">{batch.total_agencies ?? "—"}</td>
                      <td className="px-3 py-2">
                        <StatusBadge status={batch.status} />
                      </td>
                      <td className="px-3 py-2 text-xs text-gray-500">
                        {batch.processed_at ? new Date(batch.processed_at).toLocaleString("es-AR") : "—"}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Side panel */}
      {isPanelOpen && (
        <div className="w-80 flex-shrink-0 bg-white border-l shadow-lg ml-5 rounded-xl overflow-y-auto max-h-[calc(100vh-120px)] sticky top-4 self-start">
          <div className="flex items-center justify-between px-4 py-3 border-b bg-gray-50">
            <h3 className="text-sm font-semibold text-gray-700">Detalle Lote #{selectedBatch.id}</h3>
            <button onClick={handleClosePanel} className="text-gray-400 hover:text-gray-600 p-1 rounded">
              <X size={16} />
            </button>
          </div>

          {detailLoading ? (
            <div className="p-4 text-center text-sm text-gray-400">Cargando detalle...</div>
          ) : (
            <div className="p-4 space-y-4">
              {/* Batch info */}
              <div className="space-y-1.5">
                <p className="text-xs text-gray-500">Archivo</p>
                <p className="text-sm font-medium text-gray-800 break-all">{selectedBatch.zip_filename}</p>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <p className="text-xs text-gray-500">Fecha Operación</p>
                  <p className="text-sm">{selectedBatch.operation_date || "—"}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Resumen</p>
                  <p className="text-sm font-mono">{selectedBatch.resumen_number || "—"}</p>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <p className="text-xs text-gray-500">Registros</p>
                  <p className="text-sm">{selectedBatch.total_detail_records ?? "—"}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Agencias</p>
                  <p className="text-sm">{selectedBatch.total_agencies ?? "—"}</p>
                </div>
              </div>
              <div>
                <p className="text-xs text-gray-500 mb-1">Estado</p>
                <StatusBadge status={selectedBatch.status} />
              </div>

              {selectedBatch.error_message && (
                <div className="bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                  <p className="text-xs text-red-700">{selectedBatch.error_message}</p>
                </div>
              )}

              {/* Validations */}
              {validaciones.length > 0 && (
                <div className="space-y-2">
                  <p className="text-xs font-semibold text-gray-700">Validaciones</p>
                  {validaciones
                    .filter((v) => v.validation_type !== "DETAIL_VS_SUMMARY" || !v.passed)
                    .map((v) => (
                      <div key={v.id} className={`flex items-start gap-2 border rounded-lg px-3 py-2 text-xs ${v.passed ? "bg-green-50 border-green-200" : "bg-red-50 border-red-200"}`}>
                        {v.passed ? (
                          <CheckCircle size={14} className="text-green-600 mt-0.5 flex-shrink-0" />
                        ) : (
                          <XCircle size={14} className="text-red-600 mt-0.5 flex-shrink-0" />
                        )}
                        <div>
                          <p className="font-medium">{v.validation_type}</p>
                          <p className="text-gray-600 mt-0.5">{v.detail_message}</p>
                        </div>
                      </div>
                    ))}
                  {validaciones.filter((v) => v.validation_type === "DETAIL_VS_SUMMARY" && v.passed).length > 0 && (
                    <div className="flex items-center gap-2 border rounded-lg px-3 py-2 text-xs bg-green-50 border-green-200">
                      <CheckCircle size={14} className="text-green-600 flex-shrink-0" />
                      <p className="font-medium">
                        DETAIL_VS_SUMMARY: {validaciones.filter((v) => v.validation_type === "DETAIL_VS_SUMMARY" && v.passed).length} agencias OK
                      </p>
                    </div>
                  )}
                </div>
              )}

              {/* Agency summary */}
              {agencyList.length > 0 && (
                <div className="space-y-2">
                  <p className="text-xs font-semibold text-gray-700">Resumen por Agencia ({agencyList.length})</p>
                  <div className="max-h-48 overflow-y-auto space-y-1">
                    {agencyList.map((ag) => (
                      <div key={ag.n_agen} className="flex items-center justify-between border rounded px-2 py-1.5 text-xs bg-white">
                        <span className="font-mono text-gray-700">{ag.n_agen}</span>
                        <span className="font-mono text-gray-600">{fmt(ag.total)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Files */}
              {archivos.length > 0 && (
                <div className="space-y-2">
                  <p className="text-xs font-semibold text-gray-700">Archivos</p>
                  {archivos
                    .filter((a) => a.file_type.startsWith("PDF"))
                    .map((a) => (
                      <a
                        key={a.id}
                        href={getArchivoUrl(selectedBatch.id, a.id)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-2 border rounded-lg px-3 py-2 text-xs text-gray-700 hover:bg-gray-50"
                      >
                        <Download size={13} className="flex-shrink-0" />
                        <span className="truncate">{a.original_filename}</span>
                      </a>
                    ))}
                </div>
              )}

              {/* Retry button */}
              {selectedBatch.status === "VALIDADO" && (
                <PermissionGate moduleCode="liquidaciones" action="liq:write">
                  <button
                    onClick={handleRetry}
                    disabled={retryLoading}
                    className="flex items-center justify-center gap-2 w-full px-3 py-1.5 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                  >
                    <RefreshCw size={14} />
                    {retryLoading ? "Reenviando..." : "Reenviar a Conciliación"}
                  </button>
                </PermissionGate>
              )}
            </div>
          )}
        </div>
      )}

      {/* Process modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="fixed inset-0 bg-black/30" onClick={() => !processLoading && setShowModal(false)} />
          <div className="relative bg-white rounded-xl shadow-xl w-full max-w-md mx-4 p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-800">Procesar Liquidación</h3>
              <button
                onClick={() => !processLoading && setShowModal(false)}
                className="text-gray-400 hover:text-gray-600 p-1 rounded"
              >
                <X size={18} />
              </button>
            </div>

            {/* Mode tabs */}
            <div className="flex border rounded-lg overflow-hidden">
              <button
                onClick={() => setProcessMode("upload")}
                className={`flex-1 px-3 py-2 text-sm font-medium flex items-center justify-center gap-2 ${processMode === "upload" ? "bg-blue-50 text-blue-700" : "text-gray-600 hover:bg-gray-50"}`}
              >
                <Upload size={14} />
                Subir archivo
              </button>
              <button
                onClick={() => setProcessMode("path")}
                className={`flex-1 px-3 py-2 text-sm font-medium flex items-center justify-center gap-2 ${processMode === "path" ? "bg-blue-50 text-blue-700" : "text-gray-600 hover:bg-gray-50"}`}
              >
                <FolderOpen size={14} />
                Ruta del archivo
              </button>
            </div>

            {processMode === "upload" ? (
              <div>
                <label className="text-sm text-gray-600 block mb-2">Seleccionar archivo ZIP</label>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".zip"
                  onChange={handleProcessUpload}
                  disabled={processLoading}
                  className="w-full text-sm text-gray-500 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
                />
              </div>
            ) : (
              <div className="space-y-3">
                <div>
                  <label className="text-sm text-gray-600 block mb-1">Ruta del archivo ZIP</label>
                  <input
                    type="text"
                    value={zipPath}
                    onChange={(e) => setZipPath(e.target.value)}
                    placeholder="/data/externalfiles/archive.zip"
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <button
                  onClick={handleProcessPath}
                  disabled={processLoading || !zipPath.trim()}
                  className="w-full px-3 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                >
                  {processLoading ? "Procesando..." : "Procesar"}
                </button>
              </div>
            )}

            {processLoading && processMode === "upload" && (
              <p className="text-sm text-blue-600 text-center">Procesando archivo...</p>
            )}

            {processError && (
              <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-3 py-2 text-sm">
                {processError}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
