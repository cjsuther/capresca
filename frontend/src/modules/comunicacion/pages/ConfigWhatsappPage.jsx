import { useEffect, useState } from "react";
import { Eye, EyeOff, Save, CheckCircle, AlertCircle } from "lucide-react";
import { getWhatsappConfig, updateWhatsappConfig } from "../../../api/comunicacion";

const INITIAL = {
  phone_number_id: "",
  business_account_id: "",
  access_token: "",
  webhook_verify_token: "",
  app_secret: "",
  display_phone_number: "",
};

export default function ConfigWhatsappPage() {
  const [config, setConfig] = useState(null);
  const [form, setForm] = useState(INITIAL);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showToken, setShowToken] = useState(false);
  const [showSecret, setShowSecret] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      const data = await getWhatsappConfig();
      setConfig(data);
      setForm({
        phone_number_id: data.phone_number_id || "",
        business_account_id: data.business_account_id || "",
        access_token: "",  // nunca llega en claro
        webhook_verify_token: data.webhook_verify_token || "",
        app_secret: "",    // nunca llega en claro
        display_phone_number: data.display_phone_number || "",
      });
    } catch {
      // no hay config aún
      setConfig(null);
      setForm(INITIAL);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    if (!config && !form.access_token) {
      setError("El Access Token es requerido en la primera configuración.");
      return;
    }
    setSaving(true);
    try {
      const data = await updateWhatsappConfig({
        phone_number_id: form.phone_number_id,
        business_account_id: form.business_account_id,
        webhook_verify_token: form.webhook_verify_token,
        display_phone_number: form.display_phone_number || null,
        access_token: form.access_token || null,
        app_secret: form.app_secret || null,
      });
      setConfig(data);
      setForm({ ...form, access_token: "", app_secret: "" });
      setSuccess("Configuración guardada correctamente");
      setTimeout(() => setSuccess(""), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || "Error al guardar");
    } finally {
      setSaving(false);
    }
  };

  const f = (field) => ({
    value: form[field],
    onChange: (e) => setForm({ ...form, [field]: e.target.value }),
  });

  if (loading) {
    return <div className="p-6 text-center text-gray-400">Cargando configuración...</div>;
  }

  const tokenStored = Boolean(config?.access_token_masked && config.access_token_masked !== "***");
  const secretStored = Boolean(config?.has_app_secret);

  return (
    <div className="max-w-2xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-gray-900">Configuración WhatsApp</h1>
      </div>

      {/* Estado actual */}
      {config ? (
        <div className="bg-green-50 border border-green-200 rounded-xl p-4 mb-5 flex items-center gap-3">
          <CheckCircle size={20} className="text-green-600" />
          <div className="text-sm">
            <p className="font-medium text-green-800">WhatsApp configurado</p>
            <p className="text-xs text-green-700 font-mono">
              {config.display_phone_number || "(sin número visible)"} · Token: {config.access_token_masked}
              {config.has_app_secret && " · App Secret cargado"}
            </p>
          </div>
        </div>
      ) : (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 mb-5 flex items-center gap-3">
          <AlertCircle size={20} className="text-amber-600" />
          <div className="text-sm">
            <p className="font-medium text-amber-800">WhatsApp no configurado</p>
            <p className="text-xs text-amber-700">
              Cargá las credenciales de tu app de Meta para empezar a enviar/recibir mensajes.
            </p>
          </div>
        </div>
      )}

      {error && <div className="mb-4 p-3 text-sm bg-red-50 text-red-600 rounded-lg">{error}</div>}
      {success && <div className="mb-4 p-3 text-sm bg-green-50 text-green-600 rounded-lg">{success}</div>}

      <form onSubmit={handleSubmit} className="bg-white border rounded-xl p-5 space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Phone Number ID</label>
          <input
            className="w-full px-3 py-2 text-sm border rounded-lg font-mono focus:outline-none focus:ring-1 focus:ring-blue-300"
            placeholder="123456789012345"
            {...f("phone_number_id")}
            required
          />
          <p className="text-xs text-gray-400 mt-1">Meta → WhatsApp → API Setup → Phone number ID.</p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Business Account ID</label>
          <input
            className="w-full px-3 py-2 text-sm border rounded-lg font-mono focus:outline-none focus:ring-1 focus:ring-blue-300"
            placeholder="123456789012345"
            {...f("business_account_id")}
            required
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Access Token {tokenStored && <span className="text-gray-400 font-normal text-xs">(dejá vacío para mantener el guardado)</span>}
          </label>
          <div className="relative">
            <input
              type={showToken ? "text" : "password"}
              className="w-full px-3 py-2 pr-10 text-sm border rounded-lg font-mono focus:outline-none focus:ring-1 focus:ring-blue-300"
              placeholder={tokenStored ? "•••••••••••• (guardado)" : "EAAxxxxxxxxxxxx..."}
              {...f("access_token")}
            />
            <button type="button" onClick={() => setShowToken(!showToken)} className="absolute right-3 top-2.5 text-gray-400 hover:text-gray-600">
              {showToken ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>
          <p className="text-xs text-gray-400 mt-1">
            Token permanente (System User Token) de Meta. Se usa para enviar mensajes y descargar media.
          </p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Webhook Verify Token</label>
          <input
            className="w-full px-3 py-2 text-sm border rounded-lg font-mono focus:outline-none focus:ring-1 focus:ring-blue-300"
            placeholder="cualquier string que vos elijas"
            {...f("webhook_verify_token")}
            required
          />
          <p className="text-xs text-gray-400 mt-1">
            Mismo valor que cargás en Meta → Webhooks → Verify token cuando suscribís el webhook.
          </p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            App Secret <span className="text-gray-400 font-normal text-xs">(opcional, valida la firma del webhook)</span>
            {secretStored && <span className="text-gray-400 font-normal text-xs"> · dejá vacío para mantener el guardado</span>}
          </label>
          <div className="relative">
            <input
              type={showSecret ? "text" : "password"}
              className="w-full px-3 py-2 pr-10 text-sm border rounded-lg font-mono focus:outline-none focus:ring-1 focus:ring-blue-300"
              placeholder={secretStored ? "•••••••••••• (guardado)" : "App Secret de Meta"}
              {...f("app_secret")}
            />
            <button type="button" onClick={() => setShowSecret(!showSecret)} className="absolute right-3 top-2.5 text-gray-400 hover:text-gray-600">
              {showSecret ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>
          <p className="text-xs text-gray-400 mt-1">
            Si no lo cargás, la firma del webhook no se valida (no recomendado en producción).
          </p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Número visible <span className="text-gray-400 font-normal text-xs">(sólo para mostrar en la UI)</span>
          </label>
          <input
            className="w-full px-3 py-2 text-sm border rounded-lg font-mono focus:outline-none focus:ring-1 focus:ring-blue-300"
            placeholder="+54 9 11 5..."
            {...f("display_phone_number")}
          />
        </div>

        <div className="flex justify-end pt-2">
          <button
            type="submit"
            disabled={saving}
            className="flex items-center gap-2 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            <Save size={15} />
            {saving ? "Guardando..." : "Guardar"}
          </button>
        </div>
      </form>
    </div>
  );
}
