import axios from "axios";
import { useAuthStore } from "../context/authStore";
import { useStepUpStore } from "../context/stepUpStore";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api",
  timeout: 15000,
});

// Respuestas del gateway que piden el doble factor para una operación sensible.
export const CODIGOS_STEP_UP = ["step_up_requerido", "2fa_requerido"];

// Inyectar token en cada request (y el de step-up, si hay uno vigente, en las que modifican algo)
api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  const metodo = (config.method || "get").toLowerCase();
  if (metodo !== "get") {
    const stepUp = useStepUpStore.getState().tokenVigente();
    if (stepUp) config.headers["X-2FA-Token"] = stepUp;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const { response, config } = error;
    // Step-up: abrir el modal del código y, si lo confirma, repetir la operación una sola vez.
    if (response?.status === 403 && CODIGOS_STEP_UP.includes(response.data?.code) && config && !config._stepUp) {
      try {
        const token = await useStepUpStore.getState().solicitar(response.data);
        config._stepUp = true;
        config.headers["X-2FA-Token"] = token;
        return await api.request(config);
      } catch (e) {
        if (e?.response) return Promise.reject(e);
        return Promise.reject(error);   // canceló el modal: la operación no se hizo
      }
    }
    // 401 → logout automático
    if (response?.status === 401) {
      useAuthStore.getState().logout();
      useStepUpStore.getState().olvidar();
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

export default api;
