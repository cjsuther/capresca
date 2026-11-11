import { useEffect, useState } from "react";
import { ShieldCheck, ShieldOff, X, KeyRound } from "lucide-react";
import { useAuthStore } from "../../context/authStore";
import { useStepUpStore } from "../../context/stepUpStore";
import {
  getEstado2fa, enrolar2fa, activar2fa, regenerarCodigos, desactivar2fa, mensajeError2fa,
} from "../../api/dobleFactor";
import { CampoCodigo, codigoCompleto } from "./CampoCodigo";
import { EnrolarDobleFactor } from "./EnrolarDobleFactor";
import { CodigosRecuperacion } from "./CodigosRecuperacion";

/** "Doble factor" del menú del usuario: activar, códigos de recuperación y desactivar. */
export function DobleFactorModal({ onClose }) {
  const setToken = useAuthStore((s) => s.setToken);
  const setMfa = useAuthStore((s) => s.setMfa);
  const username = useAuthStore((s) => s.user?.username);
  const olvidarStepUp = useStepUpStore((s) => s.olvidar);

  const [estado, setEstado] = useState(null);
  const [vista, setVista] = useState("estado");        // estado | enrolar | codigos | regenerar | desactivar
  const [codigos, setCodigos] = useState([]);
  const [code, setCode] = useState("");
  const [recuperacion, setRecuperacion] = useState(false);
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);

  const cargar = () => getEstado2fa()
    .then((e) => { setEstado(e); setMfa({ habilitado: e.habilitado, activo: e.activo }); })
    .catch((err) => setError(mensajeError2fa(err, "No se pudo consultar el doble factor")));

  useEffect(() => { cargar(); }, []);   // eslint-disable-line react-hooks/exhaustive-deps

  const nuevaSesion = (r) => {
    olvidarStepUp();
    if (r?.access_token) setToken(r.access_token);
  };

  const activado = (r) => {
    nuevaSesion(r);
    setCodigos(r.recovery_codes || []);
    setVista("codigos");
    cargar();
  };

  const conCodigo = (accion) => async (e) => {
    e.preventDefault();
    if (!codigoCompleto(code, recuperacion)) { setError("Ingresá el código completo."); return; }
    setEnviando(true);
    setError("");
    try {
      await accion(code);
    } catch (err) {
      setError(mensajeError2fa(err));
      setCode("");
    } finally {
      setEnviando(false);
    }
  };

  const regenerar = conCodigo(async (c) => {
    const r = await regenerarCodigos(c);
    setCodigos(r.recovery_codes || []);
    setVista("codigos");
  });

  const desactivar = conCodigo(async (c) => {
    nuevaSesion(await desactivar2fa(c));
    setVista("estado");
    setCode("");
    await cargar();
  });

  const irA = (v) => { setVista(v); setCode(""); setError(""); setRecuperacion(false); };

  const formCodigo = (onSubmit, boton, peligro = false) => (
    <form onSubmit={onSubmit} className="space-y-4">
      <CampoCodigo value={code} onChange={setCode} recuperacion={recuperacion} />
      <button type="button" onClick={() => { setRecuperacion(!recuperacion); setCode(""); }}
              className="text-xs text-blue-600 hover:underline">
        {recuperacion ? "Usar el código de la app" : "Usar un código de recuperación"}
      </button>
      {error && <div role="alert" className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-3 py-2 text-sm">{error}</div>}
      <div className="flex gap-2 justify-end">
        <button type="button" onClick={() => irA("estado")} className="px-4 py-2 text-sm text-gray-600 border rounded-lg hover:bg-gray-50">
          Volver
        </button>
        <button type="submit" disabled={enviando}
                className={`px-4 py-2 text-sm text-white rounded-lg disabled:opacity-50 ${
                  peligro ? "bg-red-600 hover:bg-red-700" : "bg-blue-600 hover:bg-blue-700"}`}>
          {enviando ? "Verificando…" : boton}
        </button>
      </div>
    </form>
  );

  return (
    <div role="dialog" aria-modal="true" aria-label="Doble factor"
         className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-surface rounded-2xl shadow-xl w-full max-w-md">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <div className="flex items-center gap-2 text-gray-800 font-medium">
            <ShieldCheck size={18} /> Doble factor
          </div>
          <button onClick={onClose} aria-label="Cerrar" className="text-gray-400 hover:text-gray-600"><X size={18} /></button>
        </div>

        <div className="px-6 py-5 space-y-4">
          {!estado && !error && <p className="text-sm text-gray-400">Cargando…</p>}
          {!estado && error && <div role="alert" className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-3 py-2 text-sm">{error}</div>}

          {estado && !estado.habilitado && (
            <p className="text-sm text-gray-600">El doble factor no está habilitado en el sistema.</p>
          )}

          {estado?.habilitado && vista === "estado" && (
            <>
              {estado.activo ? (
                <p className="flex items-center gap-2 text-sm text-green-700 bg-green-50 border border-green-200 rounded-lg px-3 py-2">
                  <ShieldCheck size={16} /> Activo
                  {estado.activado_en && <span className="text-green-600">desde el {new Date(estado.activado_en).toLocaleDateString("es-AR")}</span>}
                </p>
              ) : (
                <p className="flex items-center gap-2 text-sm text-gray-600 bg-gray-50 border rounded-lg px-3 py-2">
                  <ShieldOff size={16} /> No activado
                  {estado.obligatorio && <strong className="text-amber-700">· tu rol lo exige</strong>}
                </p>
              )}
              <p className="text-sm text-gray-500">
                Además de la contraseña, al ingresar y en las operaciones sensibles se te pide el código de 6 dígitos
                de Google Authenticator o Microsoft Authenticator.
              </p>
              {error && <div role="alert" className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-3 py-2 text-sm">{error}</div>}
              <div className="flex flex-wrap gap-2 justify-end">
                {estado.activo ? (
                  <>
                    <button onClick={() => irA("regenerar")}
                            className="flex items-center gap-1.5 px-3 py-2 text-sm border rounded-lg hover:bg-gray-50">
                      <KeyRound size={14} /> Códigos de recuperación nuevos
                    </button>
                    {!estado.obligatorio && (
                      <button onClick={() => irA("desactivar")}
                              className="px-3 py-2 text-sm text-red-600 border border-red-200 rounded-lg hover:bg-red-50">
                        Desactivar
                      </button>
                    )}
                  </>
                ) : (
                  <button onClick={() => irA("enrolar")}
                          className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700">
                    Activar doble factor
                  </button>
                )}
              </div>
            </>
          )}

          {vista === "enrolar" && (
            <EnrolarDobleFactor enrolar={enrolar2fa} activar={activar2fa} onActivado={activado}
                                onCancelar={() => irA("estado")} />
          )}

          {vista === "codigos" && (
            <>
              <CodigosRecuperacion codigos={codigos} usuario={username} />
              <div className="flex justify-end">
                <button onClick={() => irA("estado")} className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700">
                  Listo, ya los guardé
                </button>
              </div>
            </>
          )}

          {vista === "regenerar" && (
            <>
              <p className="text-sm text-gray-600">Los códigos anteriores dejan de servir. Confirmá con un código:</p>
              {formCodigo(regenerar, "Generar códigos nuevos")}
            </>
          )}

          {vista === "desactivar" && (
            <>
              <p className="text-sm text-gray-600">
                Sin doble factor tu cuenta queda protegida sólo por la contraseña, y las operaciones sensibles
                pueden quedar bloqueadas hasta que lo vuelvas a activar. Confirmá con un código:
              </p>
              {formCodigo(desactivar, "Desactivar", true)}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
