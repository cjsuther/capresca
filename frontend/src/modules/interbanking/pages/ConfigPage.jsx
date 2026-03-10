import { useEffect, useState } from "react";
import { getConfig, saveConfig, testConfig, getTokenStatus } from "../../../api/interbanking";
import { Eye, EyeOff, CheckCircle, XCircle } from "lucide-react";
import { PermissionGate } from "../../../components/PrivateRoute";

const INITIAL_FORM = {
  name: "",
  base_url: "",
  auth_url: "https://preauth.interbanking.com.ar",
  client_id: "",
  username: "",
  password: "",
  scope: "transferencias-confeccion",
  service_url: "",
};

export default function ConfigPage() {
  const [config, setConfig] = useState(null);
  const [tokenStatus, setTokenStatus] = useState(null);
  const [form, setForm] = useState(INITIAL_FORM);
  const [showPassword, setShowPassword] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const load = async () => {
    try {
      const data = await getConfig();
      setConfig(data);
      setForm({
        name: data.name,
        base_url: data.base_url,
        auth_url: data.auth_url || "https://preauth.interbanking.com.ar",
        client_id: data.client_id,
        username: data.username || "",
        password: "",
        scope: data.scope || "transferencias-confeccion",
        service_url: data.service_url || "",
      });
    } catch {
      // No hay config aún
    }
    try {
      const status = await getTokenStatus();
      setTokenStatus(status);
    } catch {}
  };

  useEffect(() => { load(); }, []);

  const handleSave = async (e) => {
    e.preventDefault();
    if (!form.password) { setError("Ingresá la contraseña"); return; }
    if (!form.username) { setError("Ingresá el usuario"); return; }
    setError("");
    setSuccess("");
    setSaving(true);
    try {
      await saveConfig(form);
      setSuccess("Configuración guardada correctamente");
      load();
    } catch (err) {
      setError(err.response?.data?.detail || "Error al guardar");
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    if (!form.password) { setError("Ingresá la contraseña para probar"); return; }
    if (!form.username) { setError("Ingresá el usuario para probar"); return; }
    setError("");
    setTestResult(null);
    setTesting(true);
    try {
      const result = await testConfig(form);
      setTestResult(result);
    } catch (err) {
      setTestResult({ success: false, error: err.response?.data?.detail || "Error de conexión" });
    } finally {
      setTesting(false);
    }
  };

  const f = (field) => ({
    value: form[field],
    onChange: (e) => setForm({ ...form, [field]: e.target.value }),
  });

  return (
    <div className="max-w-2xl">
      <h2 className="text-xl font-semibold text-gray-800 mb-6">Configuración Interbanking</h2>

      {/* Estado del token */}
      {tokenStatus !== null && (
        <div className={`rounded-xl p-4 mb-6 flex items-center gap-3 ${tokenStatus.has_active_token ? "bg-green-50 border border-green-200" : "bg-yellow-50 border border-yellow-200"}`}>
          {tokenStatus.has_active_token
            ? <CheckCircle size={18} className="text-green-600" />
            : <XCircle size={18} className="text-yellow-600" />
          }
          <div>
            <p className={`text-sm font-medium ${tokenStatus.has_active_token ? "text-green-800" : "text-yellow-800"}`}>
              {tokenStatus.has_active_token
                ? `Token activo — vence en ${tokenStatus.minutes_remaining} minutos`
                : "Sin token activo"
              }
            </p>
            {tokenStatus.expires_at && (
              <p className="text-xs text-gray-500">{new Date(tokenStatus.expires_at).toLocaleString()}</p>
            )}
          </div>
        </div>
      )}

      {error && <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-2 text-sm mb-4">{error}</div>}
      {success && <div className="bg-green-50 border border-green-200 text-green-700 rounded-lg px-4 py-2 text-sm mb-4">{success}</div>}
      {testResult && (
        <div className={`rounded-lg px-4 py-3 text-sm mb-4 ${testResult.success ? "bg-green-50 border border-green-200 text-green-800" : "bg-red-50 border border-red-200 text-red-700"}`}>
          {testResult.success
            ? <><strong>Conexión exitosa.</strong> Token: {testResult.token_preview} (expira en {testResult.expires_in}s)</>
            : <><strong>Error:</strong> {testResult.error}</>
          }
        </div>
      )}

      <PermissionGate moduleCode="interbanking" action="config:write"
        fallback={
          config ? (
            <div className="bg-white border rounded-xl p-5">
              <dl className="space-y-3 text-sm">
                <div className="flex justify-between"><dt className="text-gray-500">Nombre</dt><dd>{config.name}</dd></div>
                <div className="flex justify-between"><dt className="text-gray-500">URL Base API</dt><dd className="font-mono text-xs">{config.base_url}</dd></div>
                <div className="flex justify-between"><dt className="text-gray-500">URL Auth</dt><dd className="font-mono text-xs">{config.auth_url}</dd></div>
                <div className="flex justify-between"><dt className="text-gray-500">Client ID</dt><dd className="font-mono text-xs">{config.client_id}</dd></div>
                <div className="flex justify-between"><dt className="text-gray-500">Usuario</dt><dd className="font-mono text-xs">{config.username}</dd></div>
                <div className="flex justify-between"><dt className="text-gray-500">Scope</dt><dd className="font-mono text-xs">{config.scope}</dd></div>
              </dl>
            </div>
          ) : <p className="text-gray-400 text-sm">Sin configuración</p>
        }
      >
        <form onSubmit={handleSave} className="bg-white border rounded-xl p-5 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Nombre de la configuración</label>
            <input className="input w-full" placeholder="Ej: Sandbox Portezuelo" {...f("name")} required />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">URL Base API</label>
              <input className="input w-full font-mono text-sm" placeholder="https://api.interbanking.com.ar" {...f("base_url")} required />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">URL Auth (preauth)</label>
              <input className="input w-full font-mono text-sm" placeholder="https://preauth.interbanking.com.ar" {...f("auth_url")} required />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Client ID</label>
            <input className="input w-full font-mono text-sm" {...f("client_id")} required />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Usuario</label>
              <input className="input w-full font-mono text-sm" placeholder="-3|...|sandbox" {...f("username")} required />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Contraseña {config && <span className="text-gray-400 font-normal text-xs">(requerida al guardar)</span>}
              </label>
              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  className="input w-full pr-10 font-mono text-sm"
                  placeholder={config ? "••••••••••••" : "Contraseña"}
                  value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })}
                />
                <button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute right-3 top-2.5 text-gray-400 hover:text-gray-600">
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Scope</label>
              <input className="input w-full font-mono text-sm" placeholder="transferencias-confeccion" {...f("scope")} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Service URL <span className="text-gray-400 font-normal text-xs">(header)</span></label>
              <input className="input w-full font-mono text-sm" placeholder="https://..." {...f("service_url")} />
            </div>
          </div>
          <div className="flex gap-2 justify-end pt-2">
            <button
              type="button"
              onClick={handleTest}
              disabled={testing}
              className="px-4 py-2 text-sm text-gray-600 border rounded-lg hover:bg-gray-50 disabled:opacity-50"
            >
              {testing ? "Probando..." : "Probar Conexión"}
            </button>
            <button
              type="submit"
              disabled={saving}
              className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {saving ? "Guardando..." : "Guardar"}
            </button>
          </div>
        </form>
      </PermissionGate>
    </div>
  );
}
