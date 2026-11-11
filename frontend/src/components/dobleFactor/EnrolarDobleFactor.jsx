import { useEffect, useState } from "react";
import { Smartphone, RefreshCw } from "lucide-react";
import { CampoCodigo, codigoCompleto } from "./CampoCodigo";
import { mensajeError2fa } from "../../api/dobleFactor";

/**
 * Enrolamiento: pide el QR, el usuario lo escanea con Google o Microsoft Authenticator y confirma con el
 * primer código. Se usa en el perfil y en el login (2FA obligatorio).
 *   enrolar()                 → { token_id, qr_png_base64, secret, ... }
 *   activar(tokenId, code)    → lo que devuelva el backend (pasa a onActivado)
 */
export function EnrolarDobleFactor({ enrolar, activar, onActivado, onCancelar }) {
  const [enrolamiento, setEnrolamiento] = useState(null);
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [cargando, setCargando] = useState(true);
  const [enviando, setEnviando] = useState(false);

  const pedirQr = async () => {
    setCargando(true);
    setError("");
    setCode("");
    try {
      setEnrolamiento(await enrolar());
    } catch (err) {
      setEnrolamiento(null);
      setError(mensajeError2fa(err, "No se pudo generar el código QR"));
    } finally {
      setCargando(false);
    }
  };

  useEffect(() => { pedirQr(); }, []);   // eslint-disable-line react-hooks/exhaustive-deps

  const confirmar = async (e) => {
    e.preventDefault();
    if (!codigoCompleto(code)) { setError("Ingresá los 6 dígitos que muestra la app."); return; }
    setEnviando(true);
    setError("");
    try {
      onActivado(await activar(enrolamiento.token_id, code));
    } catch (err) {
      if (err?.response?.data?.code === "enrolamiento_vencido") setEnrolamiento(null);
      setError(mensajeError2fa(err));
    } finally {
      setEnviando(false);
    }
  };

  const secretoEnGrupos = (enrolamiento?.secret || "").match(/.{1,4}/g)?.join(" ");

  return (
    <form onSubmit={confirmar} className="space-y-4">
      <ol className="text-sm text-gray-600 list-decimal pl-5 space-y-1">
        <li>Instalá <strong>Google Authenticator</strong> o <strong>Microsoft Authenticator</strong> en tu celular.</li>
        <li>Escaneá el código QR (o cargá la clave a mano).</li>
        <li>Ingresá el código de 6 dígitos que aparece en la app.</li>
      </ol>

      {cargando && <p className="text-sm text-gray-400 text-center py-8">Generando código QR…</p>}

      {!cargando && enrolamiento && (
        <div className="flex flex-col items-center gap-2">
          <img src={`data:image/png;base64,${enrolamiento.qr_png_base64}`} alt="Código QR para la app autenticadora"
               className="w-44 h-44 border rounded-lg bg-white p-1" />
          <p className="text-xs text-gray-500 text-center">
            Clave para cargar a mano: <span className="font-mono text-gray-700 select-all">{secretoEnGrupos}</span>
          </p>
        </div>
      )}

      {!cargando && !enrolamiento && (
        <button type="button" onClick={pedirQr}
                className="w-full flex items-center justify-center gap-2 px-3 py-2 text-sm border rounded-lg hover:bg-gray-50">
          <RefreshCw size={14} /> Generar un código QR nuevo
        </button>
      )}

      {enrolamiento && <CampoCodigo value={code} onChange={setCode} autoFocus={false} />}

      {error && (
        <div role="alert" className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-3 py-2 text-sm">{error}</div>
      )}

      <div className="flex gap-2 justify-end">
        {onCancelar && (
          <button type="button" onClick={onCancelar} className="px-4 py-2 text-sm text-gray-600 border rounded-lg hover:bg-gray-50">
            Cancelar
          </button>
        )}
        <button type="submit" disabled={!enrolamiento || enviando}
                className="flex items-center gap-1.5 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50">
          <Smartphone size={14} /> {enviando ? "Verificando…" : "Activar doble factor"}
        </button>
      </div>
    </form>
  );
}
