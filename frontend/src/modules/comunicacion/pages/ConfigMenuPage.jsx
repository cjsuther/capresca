import { useState, useEffect } from "react";
import { Plus, Trash2, GripVertical, Save } from "lucide-react";
import clsx from "clsx";
import { getMenuConfig, updateMenuConfig } from "../../../api/comunicacion";

const EMPTY_OPTION = {
  option_id: "",
  title: "",
  description: "",
  sort_order: 0,
  action_type: "REPLY_TEXT",
  action_payload: { text: "" },
  requires_client: true,
  is_active: true,
};

export default function ConfigMenuPage() {
  const [greetingText, setGreetingText] = useState("");
  const [options, setOptions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [editingIdx, setEditingIdx] = useState(null);

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    setLoading(true);
    try {
      const data = await getMenuConfig();
      setGreetingText(data.greeting_text || "");
      setOptions(data.options || []);
    } catch {
      setError("No se pudo cargar la configuración");
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const payload = {
        greeting_text: greetingText,
        options: options.map((o, i) => ({ ...o, sort_order: i })),
      };
      await updateMenuConfig(payload);
      setSuccess("Configuración guardada correctamente");
      setTimeout(() => setSuccess(""), 3000);
    } catch (e) {
      setError(e.response?.data?.detail || "Error al guardar");
    } finally {
      setSaving(false);
    }
  };

  const addOption = () => {
    const newOpt = { ...EMPTY_OPTION, option_id: `opt_${Date.now()}`, sort_order: options.length };
    setOptions([...options, newOpt]);
    setEditingIdx(options.length);
  };

  const removeOption = (idx) => {
    setOptions(options.filter((_, i) => i !== idx));
    if (editingIdx === idx) setEditingIdx(null);
  };

  const updateOption = (idx, field, value) => {
    setOptions(options.map((o, i) => (i === idx ? { ...o, [field]: value } : o)));
  };

  const updatePayload = (idx, field, value) => {
    setOptions(options.map((o, i) =>
      i === idx ? { ...o, action_payload: { ...o.action_payload, [field]: value } } : o
    ));
  };

  const moveOption = (idx, dir) => {
    const newIdx = idx + dir;
    if (newIdx < 0 || newIdx >= options.length) return;
    const copy = [...options];
    [copy[idx], copy[newIdx]] = [copy[newIdx], copy[idx]];
    setOptions(copy);
    if (editingIdx === idx) setEditingIdx(newIdx);
    else if (editingIdx === newIdx) setEditingIdx(idx);
  };

  if (loading) {
    return <div className="p-6 text-center text-gray-400">Cargando configuración...</div>;
  }

  return (
    <div className="max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-gray-900">Configuración del Menú Interactivo</h1>
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-1.5 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
        >
          <Save size={15} />
          {saving ? "Guardando..." : "Guardar"}
        </button>
      </div>

      {error && <div className="mb-4 p-3 text-sm bg-red-50 text-red-600 rounded-lg">{error}</div>}
      {success && <div className="mb-4 p-3 text-sm bg-green-50 text-green-600 rounded-lg">{success}</div>}

      {/* Greeting text */}
      <div className="bg-white border rounded-xl p-4 mb-5">
        <label className="text-sm font-medium text-gray-700">Texto de bienvenida</label>
        <p className="text-xs text-gray-400 mt-0.5 mb-2">
          Este mensaje se envía cuando el cliente dice "hola" junto con las opciones del menú.
        </p>
        <textarea
          value={greetingText}
          onChange={(e) => setGreetingText(e.target.value)}
          rows={2}
          className="w-full px-3 py-2 text-sm border rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-300 resize-none"
        />
      </div>

      {/* Options */}
      <div className="bg-white border rounded-xl p-4">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-medium text-gray-700">Opciones del menú</h3>
            <p className="text-xs text-gray-400 mt-0.5">Máximo 10 opciones. El cliente verá estas opciones al escribir "hola".</p>
          </div>
          <button
            onClick={addOption}
            disabled={options.length >= 10}
            className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium bg-blue-50 text-blue-700 rounded-lg hover:bg-blue-100 disabled:opacity-50"
          >
            <Plus size={14} />
            Agregar
          </button>
        </div>

        {options.length === 0 ? (
          <div className="text-center py-8 text-sm text-gray-400">
            No hay opciones configuradas. Agrega una para empezar.
          </div>
        ) : (
          <div className="space-y-2">
            {options.map((opt, idx) => (
              <div key={opt.option_id} className="border rounded-lg">
                {/* Option header */}
                <div
                  className={clsx(
                    "flex items-center gap-2 px-3 py-2.5 cursor-pointer hover:bg-gray-50",
                    editingIdx === idx && "bg-gray-50"
                  )}
                  onClick={() => setEditingIdx(editingIdx === idx ? null : idx)}
                >
                  <div className="flex flex-col gap-0.5">
                    <button onClick={(e) => { e.stopPropagation(); moveOption(idx, -1); }} disabled={idx === 0} className="text-gray-300 hover:text-gray-500 disabled:opacity-30">
                      <GripVertical size={12} />
                    </button>
                  </div>
                  <span className="text-xs text-gray-400 font-mono w-5">{idx + 1}.</span>
                  <span className="text-sm font-medium text-gray-700 flex-1">{opt.title || "(sin título)"}</span>
                  <span className={clsx(
                    "text-[10px] px-2 py-0.5 rounded-full font-medium",
                    opt.action_type === "REPLY_TEXT" ? "bg-gray-100 text-gray-600" : "bg-purple-100 text-purple-600"
                  )}>
                    {opt.action_type === "REPLY_TEXT" ? "Texto fijo" : "Llamar módulo"}
                  </span>
                  <button
                    onClick={(e) => { e.stopPropagation(); removeOption(idx); }}
                    className="p-1 text-gray-300 hover:text-red-500"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>

                {/* Option edit form */}
                {editingIdx === idx && (
                  <div className="px-4 py-3 border-t bg-gray-50/50 space-y-3">
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="text-xs text-gray-500">ID de opción</label>
                        <input
                          type="text"
                          value={opt.option_id}
                          onChange={(e) => updateOption(idx, "option_id", e.target.value)}
                          className="w-full mt-0.5 px-2 py-1.5 text-xs border rounded focus:outline-none focus:ring-1 focus:ring-blue-300"
                        />
                      </div>
                      <div>
                        <label className="text-xs text-gray-500">Título (max 60)</label>
                        <input
                          type="text"
                          value={opt.title}
                          onChange={(e) => updateOption(idx, "title", e.target.value.slice(0, 60))}
                          className="w-full mt-0.5 px-2 py-1.5 text-xs border rounded focus:outline-none focus:ring-1 focus:ring-blue-300"
                        />
                      </div>
                    </div>

                    <div>
                      <label className="text-xs text-gray-500">Descripción (max 200)</label>
                      <input
                        type="text"
                        value={opt.description || ""}
                        onChange={(e) => updateOption(idx, "description", e.target.value.slice(0, 200))}
                        className="w-full mt-0.5 px-2 py-1.5 text-xs border rounded focus:outline-none focus:ring-1 focus:ring-blue-300"
                      />
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="text-xs text-gray-500">Tipo de acción</label>
                        <select
                          value={opt.action_type}
                          onChange={(e) => {
                            const newType = e.target.value;
                            const newPayload = newType === "REPLY_TEXT"
                              ? { text: "" }
                              : { module: "", method: "GET", url_template: "", response_template: "" };
                            setOptions(options.map((o, i) =>
                              i === idx ? { ...o, action_type: newType, action_payload: newPayload } : o
                            ));
                          }}
                          className="w-full mt-0.5 px-2 py-1.5 text-xs border rounded focus:outline-none focus:ring-1 focus:ring-blue-300"
                        >
                          <option value="REPLY_TEXT">Respuesta fija</option>
                          <option value="CALL_MODULE">Llamar módulo</option>
                        </select>
                      </div>
                      <div className="flex items-end">
                        <label className="flex items-center gap-1.5 text-xs text-gray-500 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={opt.requires_client}
                            onChange={(e) => updateOption(idx, "requires_client", e.target.checked)}
                            className="rounded"
                          />
                          Requiere cliente vinculado
                        </label>
                      </div>
                    </div>

                    {opt.action_type === "REPLY_TEXT" ? (
                      <div>
                        <label className="text-xs text-gray-500">Texto de respuesta</label>
                        <textarea
                          value={opt.action_payload?.text || ""}
                          onChange={(e) => updatePayload(idx, "text", e.target.value)}
                          rows={2}
                          className="w-full mt-0.5 px-2 py-1.5 text-xs border rounded focus:outline-none focus:ring-1 focus:ring-blue-300 resize-none"
                        />
                      </div>
                    ) : (
                      <div className="space-y-2">
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <label className="text-xs text-gray-500">Módulo</label>
                            <input
                              type="text"
                              value={opt.action_payload?.module || ""}
                              onChange={(e) => updatePayload(idx, "module", e.target.value)}
                              placeholder="conciliacion"
                              className="w-full mt-0.5 px-2 py-1.5 text-xs border rounded focus:outline-none focus:ring-1 focus:ring-blue-300"
                            />
                          </div>
                          <div>
                            <label className="text-xs text-gray-500">Método HTTP</label>
                            <select
                              value={opt.action_payload?.method || "GET"}
                              onChange={(e) => updatePayload(idx, "method", e.target.value)}
                              className="w-full mt-0.5 px-2 py-1.5 text-xs border rounded focus:outline-none focus:ring-1 focus:ring-blue-300"
                            >
                              <option value="GET">GET</option>
                              <option value="POST">POST</option>
                            </select>
                          </div>
                        </div>
                        <div>
                          <label className="text-xs text-gray-500">
                            URL template <span className="text-gray-400">(variables: {"{client_id}"}, {"{today}"})</span>
                          </label>
                          <input
                            type="text"
                            value={opt.action_payload?.url_template || ""}
                            onChange={(e) => updatePayload(idx, "url_template", e.target.value)}
                            placeholder="http://conciliacion:8006/internal/..."
                            className="w-full mt-0.5 px-2 py-1.5 text-xs border rounded focus:outline-none focus:ring-1 focus:ring-blue-300 font-mono"
                          />
                        </div>
                        <div>
                          <label className="text-xs text-gray-500">Template de respuesta</label>
                          <textarea
                            value={opt.action_payload?.response_template || ""}
                            onChange={(e) => updatePayload(idx, "response_template", e.target.value)}
                            rows={2}
                            placeholder="Estado al {date}: Adeudado ${importe_adeudado}"
                            className="w-full mt-0.5 px-2 py-1.5 text-xs border rounded focus:outline-none focus:ring-1 focus:ring-blue-300 font-mono resize-none"
                          />
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
