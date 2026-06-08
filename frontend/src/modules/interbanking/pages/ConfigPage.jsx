import { useEffect, useState } from "react";
import { getConfig, saveConfig, testConfig, getTokenStatus } from "../../../api/interbanking";
import { Eye, EyeOff, CheckCircle, XCircle } from "lucide-react";
import { PermissionGate } from "../../../components/PrivateRoute";

const INITIAL_FORM = {
  name: "",
  base_url: "https://noprod-api-gw.interbanking.com.ar/pre/sandbox",
  auth_url: "https://preauth.interbanking.com.ar",
  client_id: "",
  client_secret: "",
  username: "",
  password: "",
  service_url: "",
  customer_id: "",
};

const SCOPE_LABEL = {
  "info-financiera": "Información Financiera (cuentas, saldos, movimientos)",
  "transferencias-confeccion": "Transferencias (confección y envío)",
};

export default function ConfigPage() {
  const [config, setConfig] = useState(null);
  const [tokenStatus, setTokenStatus] = useState(null);
  const [form, setForm] = useState(INITIAL_FORM);
  const [showPassword, setShowPassword] = useState(false);
  const [showSecret, setShowSecret] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState("");  // scope que se está probando
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
        client_secret: "",
        username: data.username || "",
        password: "",
        service_url: data.service_url || "",
        customer_id: data.customer_id || "",
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

  const sameClient = config && config.client_id === form.client_id;
  const hasStoredSecret = sameClient && config?.has_client_secret;
  const hasStoredPassword = sameClient && config?.has_password && config?.username === form.username;

  const handleSave = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    setSaving(true);
    try {
      const updated = await saveConfig(form);
      setConfig(updated);
      setSuccess("Configuración guardada correctamente");
      load();
    } catch (err) {
      setError(err.response?.data?.detail || "Error al guardar");
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async (scope) => {
    setError("");
    setTestResult(null);
    setTesting(scope);
    try {
      const result = await testConfig(form, scope);
      setTestResult(result);
    } catch (err) {
      setTestResult({ success: false, scope, error: err.response?.data?.detail || "Error de conexión" });
    } finally {
      setTesting("");
    }
  };

  const f = (field) => ({
    value: form[field],
    onChange: (e) => setForm({ ...form, [field]: e.target.value }),
  });

  return (
    <div className="max-w-2xl">
      <h2 className="text-xl font-semibold text-gray-800 mb-6">Configuración Interbanking</h2>

      {/* Estado por scope */}
      {tokenStatus?.tokens?.length > 0 && (
        <div className="space-y-2 mb-6">
          {tokenStatus.tokens.map((t) => (
            <div
              key={t.scope}
              className={`rounded-xl p-3 flex items-center gap-3 ${t.has_active_token ? "bg-green-50 border border-green-200" : "bg-yellow-50 border border-yellow-200"}`}
            >
              {t.has_active_token
                ? <CheckCircle size={18} className="text-green-600" />
                : <XCircle size={18} className="text-yellow-600" />
              }
              <div className="flex-1">
                <p className={`text-sm font-medium ${t.has_active_token ? "text-green-800" : "text-yellow-800"}`}>
                  {SCOPE_LABEL[t.scope] || t.scope}
                </p>
                <p className="text-xs text-gray-500">
                  {t.has_active_token
                    ? `Token activo — vence en ${t.minutes_remaining} min (${new Date(t.expires_at).toLocaleString()})`
                    : "Sin token activo (se generará en la próxima llamada)"
                  }
                </p>
              </div>
            </div>
          ))}
        </div>
      )}

      {error && <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-2 text-sm mb-4">{error}</div>}
      {success && <div className="bg-green-50 border border-green-200 text-green-700 rounded-lg px-4 py-2 text-sm mb-4">{success}</div>}
      {testResult && (
        <div className={`rounded-lg px-4 py-3 text-sm mb-4 ${testResult.success ? "bg-green-50 border border-green-200 text-green-800" : "bg-red-50 border border-red-200 text-red-700"}`}>
          {testResult.success
            ? <><strong>OK ({testResult.scope}):</strong> token {testResult.token_preview} — expira en {testResult.expires_in}s</>
            : <><strong>Error ({testResult.scope}):</strong> {testResult.error}</>
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
                <div className="flex justify-between"><dt className="text-gray-500">Client Secret</dt><dd>{config.has_client_secret ? "•••• guardado" : "—"}</dd></div>
                <div className="flex justify-between"><dt className="text-gray-500">Usuario</dt><dd className="font-mono text-xs">{config.username || "—"}</dd></div>
                <div className="flex justify-between"><dt className="text-gray-500">Contraseña</dt><dd>{config.has_password ? "•••• guardada" : "—"}</dd></div>
                <div className="flex justify-between"><dt className="text-gray-500">Customer ID</dt><dd className="font-mono text-xs">{config.customer_id || "—"}</dd></div>
                <div className="flex justify-between"><dt className="text-gray-500">Service URL</dt><dd className="font-mono text-xs">{config.service_url || "—"}</dd></div>
              </dl>
            </div>
          ) : <p className="text-gray-400 text-sm">Sin configuración</p>
        }
      >
        <form onSubmit={handleSave} className="bg-white border rounded-xl p-5 space-y-5">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Nombre de la configuración</label>
            <input className="input w-full" placeholder="Ej: Sandbox Portezuelo" {...f("name")} required />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">URL Base API</label>
              <input className="input w-full font-mono text-sm" placeholder="https://noprod-api-gw.interbanking.com.ar/pre/sandbox" {...f("base_url")} required />
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
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Customer ID <span className="text-gray-400 font-normal text-xs">(Nº de abonado)</span>
              </label>
              <input className="input w-full font-mono text-sm" placeholder="Ej: B02072A" {...f("customer_id")} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Service URL <span className="text-gray-400 font-normal text-xs">(header)</span></label>
              <input className="input w-full font-mono text-sm" placeholder="https://sandboxcapresca.com.ar" {...f("service_url")} />
            </div>
          </div>

          {/* Sección Info Financiera */}
          <fieldset className="border rounded-lg p-4">
            <legend className="text-xs font-medium text-gray-500 px-2">
              Información Financiera · client_credentials · info-financiera
            </legend>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Client Secret {hasStoredSecret && <span className="text-gray-400 font-normal text-xs">(dejá vacío para mantener el guardado)</span>}
            </label>
            <div className="relative">
              <input
                type={showSecret ? "text" : "password"}
                className="input w-full pr-10 font-mono text-sm"
                placeholder={hasStoredSecret ? "•••••••••••• (guardado)" : "Client Secret"}
                value={form.client_secret}
                onChange={(e) => setForm({ ...form, client_secret: e.target.value })}
              />
              <button type="button" onClick={() => setShowSecret(!showSecret)} className="absolute right-3 top-2.5 text-gray-400 hover:text-gray-600">
                {showSecret ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
            <div className="mt-3 flex justify-end">
              <button
                type="button"
                onClick={() => handleTest("info-financiera")}
                disabled={!!testing}
                className="px-3 py-1.5 text-xs text-gray-600 border rounded-lg hover:bg-gray-50 disabled:opacity-50"
              >
                {testing === "info-financiera" ? "Probando..." : "Probar token info-financiera"}
              </button>
            </div>
          </fieldset>

          {/* Sección Transferencias */}
          <fieldset className="border rounded-lg p-4">
            <legend className="text-xs font-medium text-gray-500 px-2">
              Transferencias · password · transferencias-confeccion
            </legend>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Usuario</label>
                <input className="input w-full font-mono text-sm" placeholder="-3|...|sandbox" {...f("username")} />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Contraseña {hasStoredPassword && <span className="text-gray-400 font-normal text-xs">(dejá vacío para mantener la guardada)</span>}
                </label>
                <div className="relative">
                  <input
                    type={showPassword ? "text" : "password"}
                    className="input w-full pr-10 font-mono text-sm"
                    placeholder={hasStoredPassword ? "•••••••••••• (guardada)" : "Contraseña"}
                    value={form.password}
                    onChange={(e) => setForm({ ...form, password: e.target.value })}
                  />
                  <button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute right-3 top-2.5 text-gray-400 hover:text-gray-600">
                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>
            </div>
            <div className="mt-3 flex justify-end">
              <button
                type="button"
                onClick={() => handleTest("transferencias-confeccion")}
                disabled={!!testing}
                className="px-3 py-1.5 text-xs text-gray-600 border rounded-lg hover:bg-gray-50 disabled:opacity-50"
              >
                {testing === "transferencias-confeccion" ? "Probando..." : "Probar token transferencias"}
              </button>
            </div>
          </fieldset>

          <div className="flex justify-end pt-2">
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
