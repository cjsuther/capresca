import { useEffect, useRef, useState } from "react";
import { getLotes, createLote, procesarLote, getEstadoLote } from "../../../api/interbanking";
import { PermissionGate } from "../../../components/PrivateRoute";
import { Plus, Trash2, RefreshCw, ChevronDown, ChevronUp, Upload } from "lucide-react";

const STATUS_COLORS = {
  BORRADOR:   "bg-gray-100 text-gray-600",
  ENVIADO:    "bg-blue-100 text-blue-700",
  PROCESANDO: "bg-yellow-100 text-yellow-700",
  COMPLETADO: "bg-green-100 text-green-700",
  ERROR:      "bg-red-100 text-red-600",
};

const emptyItem = () => ({ cbu: "", monto: "", detalle: "" });

export default function PagosPage() {
  const [lotes, setLotes] = useState({ data: [], total: 0 });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [descripcion, setDescripcion] = useState("");
  const [items, setItems] = useState([emptyItem()]);
  const [detailId, setDetailId] = useState(null);
  const [selectedLote, setSelectedLote] = useState(null);
  const csvRef = useRef();

  const load = () => {
    setLoading(true);
    getLotes()
      .then(setLotes)
      .catch(() => setError("Error al cargar lotes"))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const addItem = () => setItems((prev) => [...prev, emptyItem()]);
  const removeItem = (i) => setItems((prev) => prev.filter((_, idx) => idx !== i));
  const updateItem = (i, field, val) =>
    setItems((prev) => prev.map((item, idx) => idx === i ? { ...item, [field]: val } : item));

  const totalAmount = items.reduce((s, i) => s + (parseFloat(i.monto) || 0), 0);

  const handleCSV = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      const lines = ev.target.result.trim().split("\n").slice(1); // skip header
      const parsed = lines.map((l) => {
        const [cbu, monto, detalle] = l.split(",");
        return { cbu: cbu?.trim() || "", monto: monto?.trim() || "", detalle: detalle?.trim() || "" };
      }).filter((i) => i.cbu);
      setItems(parsed.length ? parsed : [emptyItem()]);
    };
    reader.readAsText(file);
    e.target.value = "";
  };

  const handleCreate = async (procesar = false) => {
    setError("");
    try {
      const payload = {
        descripcion,
        items: items.map((i) => ({ cbu: i.cbu, monto: parseFloat(i.monto), detalle: i.detalle || null })),
      };
      const lote = await createLote(payload);
      if (procesar) await procesarLote(lote.id);
      setShowForm(false);
      setDescripcion("");
      setItems([emptyItem()]);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || "Error al crear lote");
    }
  };

  const handleProcesar = async (id) => {
    setError("");
    try {
      await procesarLote(id);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || "Error al procesar lote");
    }
  };

  const handleEstado = async (id) => {
    setError("");
    try {
      await getEstadoLote(id);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || "Error al consultar estado");
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold text-gray-800">Pagos en Lote</h2>
        <PermissionGate moduleCode="interbanking" action="pagos:write">
          <button
            onClick={() => setShowForm(!showForm)}
            className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700"
          >
            <Plus size={16} /> Nuevo Lote
          </button>
        </PermissionGate>
      </div>

      {error && <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-2 text-sm mb-4">{error}</div>}

      {/* Formulario */}
      {showForm && (
        <div className="bg-white border rounded-xl p-5 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-medium text-gray-700">Nuevo Lote de Pagos</h3>
            <div className="flex items-center gap-2">
              <button
                onClick={() => csvRef.current.click()}
                className="flex items-center gap-1 px-3 py-1.5 text-xs text-gray-600 border rounded-lg hover:bg-gray-50"
              >
                <Upload size={13} /> Importar CSV
              </button>
              <input ref={csvRef} type="file" accept=".csv" className="hidden" onChange={handleCSV} />
            </div>
          </div>

          <div className="mb-4">
            <label className="block text-xs font-medium text-gray-600 mb-1">Descripción</label>
            <input className="input w-full text-sm" placeholder="Descripción del lote" value={descripcion} onChange={(e) => setDescripcion(e.target.value)} />
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-sm mb-2">
              <thead>
                <tr className="text-xs text-gray-500 border-b">
                  <th className="text-left py-2 pr-3 font-medium">CBU Destino</th>
                  <th className="text-left py-2 pr-3 font-medium">Monto</th>
                  <th className="text-left py-2 pr-3 font-medium">Detalle/Referencia</th>
                  <th className="py-2"></th>
                </tr>
              </thead>
              <tbody>
                {items.map((item, i) => (
                  <tr key={i}>
                    <td className="pr-3 py-1"><input className="input w-full text-sm" placeholder="CBU (22 dígitos)" value={item.cbu} onChange={(e) => updateItem(i, "cbu", e.target.value)} /></td>
                    <td className="pr-3 py-1"><input type="number" step="0.01" min="0" className="input w-28 text-sm" placeholder="0.00" value={item.monto} onChange={(e) => updateItem(i, "monto", e.target.value)} /></td>
                    <td className="pr-3 py-1"><input className="input w-full text-sm" placeholder="Referencia" value={item.detalle} onChange={(e) => updateItem(i, "detalle", e.target.value)} /></td>
                    <td className="py-1">
                      {items.length > 1 && (
                        <button onClick={() => removeItem(i)} className="p-1 text-gray-400 hover:text-red-600">
                          <Trash2 size={14} />
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t text-sm font-medium">
                  <td className="py-2 text-gray-500">{items.length} ítem{items.length !== 1 ? "s" : ""}</td>
                  <td className="py-2 text-gray-800">$ {totalAmount.toLocaleString("es-AR", { minimumFractionDigits: 2 })}</td>
                  <td colSpan={2}></td>
                </tr>
              </tfoot>
            </table>
          </div>

          <button onClick={addItem} className="flex items-center gap-1 text-xs text-blue-600 hover:underline mb-4">
            <Plus size={12} /> Agregar ítem
          </button>

          <div className="flex gap-2 justify-end">
            <button onClick={() => setShowForm(false)} className="px-4 py-2 text-sm text-gray-600 border rounded-lg hover:bg-gray-50">Cancelar</button>
            <button
              onClick={() => handleCreate(false)}
              disabled={!descripcion || items.some((i) => !i.cbu || !i.monto)}
              className="px-4 py-2 text-sm bg-gray-600 text-white rounded-lg hover:bg-gray-700 disabled:opacity-50"
            >
              Guardar Borrador
            </button>
            <button
              onClick={() => handleCreate(true)}
              disabled={!descripcion || items.some((i) => !i.cbu || !i.monto)}
              className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              Crear y Procesar
            </button>
          </div>
        </div>
      )}

      {/* Tabla de lotes */}
      <div className="bg-white border rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-gray-600">
            <tr>
              <th className="text-left px-4 py-3 font-medium">Fecha</th>
              <th className="text-left px-4 py-3 font-medium">Descripción</th>
              <th className="text-left px-4 py-3 font-medium">ID Lote IB</th>
              <th className="text-right px-4 py-3 font-medium">Ítems</th>
              <th className="text-right px-4 py-3 font-medium">Total ($)</th>
              <th className="text-left px-4 py-3 font-medium">Estado</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400">Cargando...</td></tr>
            ) : lotes.data.length === 0 ? (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400">Sin lotes</td></tr>
            ) : lotes.data.map((lote) => (
              <>
                <tr key={lote.id} className="hover:bg-gray-50 cursor-pointer" onClick={() => setDetailId(detailId === lote.id ? null : lote.id)}>
                  <td className="px-4 py-3 text-gray-500 text-xs">{lote.created_at ? new Date(lote.created_at).toLocaleString() : "—"}</td>
                  <td className="px-4 py-3 font-medium">{lote.descripcion || "—"}</td>
                  <td className="px-4 py-3 font-mono text-xs">{lote.id_lote_ib || "—"}</td>
                  <td className="px-4 py-3 text-right">{lote.total_items ?? "—"}</td>
                  <td className="px-4 py-3 text-right font-medium">{lote.total_amount ? `$${Number(lote.total_amount).toLocaleString("es-AR", { minimumFractionDigits: 2 })}` : "—"}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${STATUS_COLORS[lote.status] || "bg-gray-100 text-gray-600"}`}>{lote.status || "—"}</span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1">
                      <PermissionGate moduleCode="interbanking" action="pagos:write">
                        {(lote.status === "BORRADOR" || lote.status === "ENVIADO") && (
                          <button
                            onClick={(e) => { e.stopPropagation(); handleProcesar(lote.id); }}
                            className="px-2 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700"
                          >
                            Procesar
                          </button>
                        )}
                      </PermissionGate>
                      {lote.id_lote_ib && (
                        <button
                          onClick={(e) => { e.stopPropagation(); handleEstado(lote.id); }}
                          className="p-1 text-gray-400 hover:text-blue-600"
                          title="Consultar estado"
                        >
                          <RefreshCw size={13} />
                        </button>
                      )}
                      {detailId === lote.id ? <ChevronUp size={14} className="text-gray-400" /> : <ChevronDown size={14} className="text-gray-400" />}
                    </div>
                  </td>
                </tr>
                {detailId === lote.id && (
                  <tr key={`${lote.id}-detail`}>
                    <td colSpan={7} className="px-4 pb-4 bg-gray-50 border-b">
                      <div className="pt-3">
                        <p className="text-xs font-medium text-gray-600 mb-2">Ítems del lote</p>
                        <table className="w-full text-xs">
                          <thead><tr className="text-gray-500 border-b">
                            <th className="text-left py-1 pr-4">CBU</th>
                            <th className="text-right py-1 pr-4">Monto</th>
                            <th className="text-left py-1 pr-4">Detalle</th>
                            <th className="text-left py-1">Estado ítem</th>
                          </tr></thead>
                          <tbody>
                            {(lote.items || []).map((item) => (
                              <tr key={item.id} className="border-b last:border-0">
                                <td className="py-1 pr-4 font-mono">{item.cbu}</td>
                                <td className="py-1 pr-4 text-right">${Number(item.monto).toLocaleString("es-AR", { minimumFractionDigits: 2 })}</td>
                                <td className="py-1 pr-4 text-gray-500">{item.detalle || "—"}</td>
                                <td className="py-1">{item.status_item || "—"}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
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
