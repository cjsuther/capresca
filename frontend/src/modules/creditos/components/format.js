// Formato es-AR compartido por las pantallas de Créditos.
export const money = (v) =>
  v == null || v === "" ? "—" : Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });

export const num = (v) => (v == null || v === "" ? "0" : Number(v).toLocaleString("es-AR"));

/** Fecha ISO (YYYY-MM-DD) o timestamp → dd/mm/aaaa. */
export const fecha = (v) => {
  if (!v) return "—";
  const d = String(v).length === 10 ? new Date(`${v}T00:00:00`) : new Date(v);
  return isNaN(d) ? String(v) : d.toLocaleDateString("es-AR");
};

export const hoy = () => new Date().toISOString().slice(0, 10);

export const fmtBytes = (n) =>
  n < 1024 ? `${n} B` : n < 1048576 ? `${(n / 1024).toFixed(0)} KB` : `${(n / 1048576).toFixed(1)} MB`;
