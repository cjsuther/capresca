import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { ShieldCheck } from "lucide-react";
import { login } from "../api/auth";
import { loginConCodigo, loginEnrolar, loginActivar, mensajeError2fa } from "../api/dobleFactor";
import { useAuthStore } from "../context/authStore";
import { useIsAuthenticated } from "../context/usePermissions";
import { ThemeToggle } from "../components/ThemeToggle";
import LogoCapresca from "../components/LogoCapresca";
import { CampoCodigo, codigoCompleto } from "../components/dobleFactor/CampoCodigo";
import { EnrolarDobleFactor } from "../components/dobleFactor/EnrolarDobleFactor";
import { CodigosRecuperacion } from "../components/dobleFactor/CodigosRecuperacion";

/**
 * Ingreso. Con el doble factor prendido puede tener pasos:
 *   clave → codigo                         (2FA activo: 6 dígitos o código de recuperación)
 *   clave → enrolar → codigos              (2FA obligatorio sin activar: QR, primer código, recuperación)
 * La sesión recién se guarda cuando el backend la emite completa.
 */
export default function LoginPage() {
  const isAuth = useIsAuthenticated();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [paso, setPaso] = useState("clave");
  const [mfaToken, setMfaToken] = useState(null);
  const [code, setCode] = useState("");
  const [recuperacion, setRecuperacion] = useState(false);
  const [sesionPendiente, setSesionPendiente] = useState(null);   // sesión lista, mostrando un aviso antes
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const setAuth = useAuthStore((s) => s.setAuth);

  if (isAuth && !sesionPendiente) return <Navigate to="/dashboard" replace />;

  const entrar = (data) => {
    setAuth(data.access_token, data.user, data.permissions, data.mfa || null);
    navigate("/dashboard");
  };

  const volverAEmpezar = (mensaje = "") => {
    setPaso("clave");
    setMfaToken(null);
    setCode("");
    setPassword("");
    setRecuperacion(false);
    setError(mensaje);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const data = await login(username, password);
      if (data.requires_2fa) {
        setMfaToken(data.mfa_token);
        setPaso("codigo");
      } else if (data.requires_enrollment) {
        setMfaToken(data.mfa_token);
        setPaso("enrolar");
      } else {
        entrar(data);
      }
    } catch (err) {
      setError(err.response?.data?.detail || "Error al iniciar sesión");
    } finally {
      setLoading(false);
    }
  };

  const enviarCodigo = async (e) => {
    e.preventDefault();
    if (!codigoCompleto(code, recuperacion)) {
      setError(recuperacion ? "El código de recuperación tiene 10 caracteres (XXXXX-XXXXX)." : "Ingresá los 6 dígitos de la app.");
      return;
    }
    setError("");
    setLoading(true);
    try {
      const data = await loginConCodigo(mfaToken, code);
      if (data.remaining_recovery_codes != null) {
        setSesionPendiente(data);
        setPaso("aviso_recuperacion");
      } else {
        entrar(data);
      }
    } catch (err) {
      if (err.response?.data?.code === "mfa_token_invalido") {
        volverAEmpezar(err.response.data.detail);
      } else {
        setError(mensajeError2fa(err));
        setCode("");
      }
    } finally {
      setLoading(false);
    }
  };

  const activado = (data) => {
    setSesionPendiente(data);
    setPaso("codigos");
  };

  const erroresEnrolar = (fn) => async (...args) => {
    try {
      return await fn(...args);
    } catch (err) {
      if (err.response?.data?.code === "mfa_token_invalido") volverAEmpezar(err.response.data.detail);
      throw err;
    }
  };

  const titulo = {
    clave: "Ingresa tus credenciales",
    codigo: "Ingresá el código de tu app autenticadora",
    enrolar: "Tu rol exige doble factor: activalo para continuar",
    codigos: "Doble factor activado",
    aviso_recuperacion: "Ingresaste con un código de recuperación",
  }[paso];

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-gray-100 relative">
      {/* El tema también se elige antes de entrar: la preferencia es del navegador, no de la sesión. */}
      <div className="absolute top-4 right-4"><ThemeToggle variante="suelto" /></div>
      <div className={`bg-surface rounded-2xl shadow-lg p-8 w-full ${paso === "clave" || paso === "codigo" ? "max-w-sm" : "max-w-md"}`}>
        <div className="mb-8 text-center">
          <img src="/logo-condor.svg" alt="Portezuelo" className="logo-marca h-16 w-auto mx-auto mb-4" />
          <h1 className="text-2xl font-bold text-gray-900">Portezuelo</h1>
          <p className="text-sm text-gray-500 mt-1">{titulo}</p>
        </div>

        {paso === "clave" && (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Usuario</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="input w-full"
                placeholder="usuario"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Contraseña</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="input w-full"
                placeholder="••••••••"
                required
              />
            </div>

            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-3 py-2 text-sm">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 rounded-lg text-sm transition-colors disabled:opacity-50"
            >
              {loading ? "Ingresando..." : "Ingresar"}
            </button>
          </form>
        )}

        {paso === "codigo" && (
          <form onSubmit={enviarCodigo} className="space-y-4">
            <CampoCodigo value={code} onChange={setCode} recuperacion={recuperacion} />
            <button type="button" onClick={() => { setRecuperacion(!recuperacion); setCode(""); setError(""); }}
                    className="text-xs text-blue-600 hover:underline">
              {recuperacion ? "Usar el código de la app" : "No tengo el celular: usar un código de recuperación"}
            </button>
            {error && (
              <div role="alert" className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-3 py-2 text-sm">{error}</div>
            )}
            <button type="submit" disabled={loading}
                    className="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 rounded-lg text-sm transition-colors disabled:opacity-50">
              <ShieldCheck size={15} /> {loading ? "Verificando..." : "Verificar"}
            </button>
            <button type="button" onClick={() => volverAEmpezar()} className="w-full text-sm text-gray-500 hover:text-gray-700">
              Volver
            </button>
          </form>
        )}

        {paso === "enrolar" && (
          <>
            {error && <div role="alert" className="mb-4 bg-red-50 border border-red-200 text-red-700 rounded-lg px-3 py-2 text-sm">{error}</div>}
            <EnrolarDobleFactor
              enrolar={erroresEnrolar(() => loginEnrolar(mfaToken))}
              activar={erroresEnrolar((tokenId, c) => loginActivar(mfaToken, tokenId, c))}
              onActivado={activado}
              onCancelar={() => volverAEmpezar()}
            />
          </>
        )}

        {paso === "codigos" && sesionPendiente && (
          <div className="space-y-4">
            <CodigosRecuperacion codigos={sesionPendiente.recovery_codes || []} usuario={username} />
            <button onClick={() => entrar(sesionPendiente)}
                    className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 rounded-lg text-sm">
              Ya los guardé, ingresar
            </button>
          </div>
        )}

        {paso === "aviso_recuperacion" && sesionPendiente && (
          <div className="space-y-4">
            <p className="text-sm text-gray-600">
              Te quedan <strong>{sesionPendiente.remaining_recovery_codes}</strong> códigos de recuperación.
              Si perdiste el celular, desde tu menú → Doble factor podés desactivarlo y volver a activarlo con el
              celular nuevo, o generar códigos nuevos.
            </p>
            <button onClick={() => entrar(sesionPendiente)}
                    className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 rounded-lg text-sm">
              Continuar
            </button>
          </div>
        )}

        <LogoCapresca className="block h-12 w-auto mx-auto mt-8 pt-6 border-t border-gray-200 box-content" />
      </div>
    </div>
  );
}
