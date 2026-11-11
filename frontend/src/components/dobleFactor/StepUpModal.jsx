import { useEffect, useState } from "react";
import { ShieldCheck, X } from "lucide-react";
import { useStepUpStore } from "../../context/stepUpStore";
import { useAuthStore } from "../../context/authStore";
import { pedirStepUp, enrolar2fa, activar2fa, mensajeError2fa } from "../../api/dobleFactor";
import { CampoCodigo, codigoCompleto } from "./CampoCodigo";
import { EnrolarDobleFactor } from "./EnrolarDobleFactor";
import { CodigosRecuperacion } from "./CodigosRecuperacion";

/**
 * Modal global del step-up. Lo abre el interceptor de la API cuando el gateway responde que la
 * operación necesita el doble factor; al confirmar, la operación se repite sola.
 * Montado una vez en App.jsx.
 */
export function StepUpModal() {
  const pedido = useStepUpStore((s) => s.pedido);
  const completar = useStepUpStore((s) => s.completar);
  const cancelar = useStepUpStore((s) => s.cancelar);
  const olvidar = useStepUpStore((s) => s.olvidar);
  const setToken = useAuthStore((s) => s.setToken);
  const setMfa = useAuthStore((s) => s.setMfa);
  const username = useAuthStore((s) => s.user?.username);

  const [modo, setModo] = useState("codigo");          // codigo | sin2fa | enrolar | codigos
  const [code, setCode] = useState("");
  const [recuperacion, setRecuperacion] = useState(false);
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [codigos, setCodigos] = useState([]);

  useEffect(() => {
    if (!pedido) return;
    setModo(pedido.code === "2fa_requerido" ? "sin2fa" : "codigo");
    setCode(""); setError(""); setRecuperacion(false); setCodigos([]);
  }, [pedido]);

  if (!pedido) return null;

  const confirmar = async (e) => {
    e.preventDefault();
    if (!codigoCompleto(code, recuperacion)) {
      setError(recuperacion ? "El código de recuperación tiene 10 caracteres." : "Ingresá los 6 dígitos de la app.");
      return;
    }
    setEnviando(true);
    setError("");
    try {
      const r = await pedirStepUp(code);
      completar(r.step_up_token, r.expires_in);
    } catch (err) {
      if (err?.response?.data?.code === "2fa_no_activo") setModo("sin2fa");
      setError(mensajeError2fa(err));
      setCode("");
    } finally {
      setEnviando(false);
    }
  };

  const activado = (r) => {
    // La sesión se renovó (ahora con segundo factor): el step-up anterior, si había, ya no vale.
    olvidar();
    if (r.access_token) setToken(r.access_token);
    setMfa({ habilitado: true, activo: true });
    setCodigos(r.recovery_codes || []);
    setModo("codigos");
  };

  const titulo = modo === "codigo" ? "Confirmá con tu doble factor" : "Doble factor requerido";

  return (
    <div role="dialog" aria-modal="true" aria-label={titulo}
         className="fixed inset-0 z-[60] flex items-center justify-center bg-black/40 p-4"
         onKeyDown={(e) => { if (e.key === "Escape" && !enviando) cancelar(); }}>
      <div className="bg-surface rounded-2xl shadow-xl w-full max-w-sm">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <div className="flex items-center gap-2 text-gray-800 font-medium">
            <ShieldCheck size={18} className="text-blue-600" /> {titulo}
          </div>
          <button onClick={() => cancelar()} aria-label="Cerrar" className="text-gray-400 hover:text-gray-600">
            <X size={18} />
          </button>
        </div>

        <div className="px-6 py-5 space-y-4">
          {pedido.operacion && (
            <p className="text-sm text-gray-700"><strong>{pedido.operacion}</strong></p>
          )}

          {modo === "codigo" && (
            <form onSubmit={confirmar} className="space-y-4">
              <p className="text-sm text-gray-500">
                Es una operación sensible: ingresá el código de tu app autenticadora. Por unos minutos no te lo
                vamos a volver a pedir.
              </p>
              <CampoCodigo value={code} onChange={setCode} recuperacion={recuperacion} />
              <button type="button" onClick={() => { setRecuperacion(!recuperacion); setCode(""); setError(""); }}
                      className="text-xs text-blue-600 hover:underline">
                {recuperacion ? "Usar el código de la app" : "No tengo el celular: usar un código de recuperación"}
              </button>
              {error && <div role="alert" className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-3 py-2 text-sm">{error}</div>}
              <div className="flex gap-2 justify-end">
                <button type="button" onClick={() => cancelar()} className="px-4 py-2 text-sm text-gray-600 border rounded-lg hover:bg-gray-50">
                  Cancelar
                </button>
                <button type="submit" disabled={enviando}
                        className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50">
                  {enviando ? "Verificando…" : "Confirmar"}
                </button>
              </div>
            </form>
          )}

          {modo === "sin2fa" && (
            <>
              {/* El gateway explica por qué (p. ej. "Para hacer cambios en Seguridad tenés que activar el
                  doble factor."); si no lo dice, el texto general. */}
              <p className="text-sm font-medium text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                {pedido.code === "2fa_requerido" && pedido.detail
                  ? pedido.detail
                  : "Esta operación exige doble factor y todavía no lo activaste."}
              </p>
              <p className="text-sm text-gray-600">
                Lleva un minuto: necesitás Google Authenticator o Microsoft Authenticator en el celular.
              </p>
              {error && <div role="alert" className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-3 py-2 text-sm">{error}</div>}
              <div className="flex gap-2 justify-end">
                <button type="button" onClick={() => cancelar()} className="px-4 py-2 text-sm text-gray-600 border rounded-lg hover:bg-gray-50">
                  Ahora no
                </button>
                <button type="button" onClick={() => { setError(""); setModo("enrolar"); }}
                        className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700">
                  Activar doble factor
                </button>
              </div>
            </>
          )}

          {modo === "enrolar" && (
            <EnrolarDobleFactor enrolar={enrolar2fa} activar={activar2fa} onActivado={activado}
                                onCancelar={() => cancelar()} />
          )}

          {modo === "codigos" && (
            <>
              <CodigosRecuperacion codigos={codigos} usuario={username} />
              <p className="text-sm text-gray-600">Para seguir con la operación, ingresá el próximo código de la app.</p>
              <div className="flex justify-end">
                <button type="button" onClick={() => { setCode(""); setModo("codigo"); }}
                        className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700">
                  Ya los guardé
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
