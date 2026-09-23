export const money = (v) =>
  v === null || v === undefined || v === "" ? "—"
    : Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });

export const fecha = (v) => {
  if (!v) return "—";
  const d = String(v).length === 10 ? new Date(`${v}T00:00:00`) : new Date(v);
  return isNaN(d) ? String(v) : d.toLocaleDateString("es-AR");
};

export const hoy = () => new Date().toISOString().slice(0, 10);

export const ESTADO_TRANSACCION = {
  PENDIENTE_CONFIGURACION: ["Falta definir cómo se contabiliza", "warn"],
  CONTABILIZADA: ["Contabilizada", "ok"],
  ERROR: ["Con error", "crit"],
  ANULADA: ["Anulada", "neutral"],
};
