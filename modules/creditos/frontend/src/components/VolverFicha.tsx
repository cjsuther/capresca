import { Link, useSearchParams } from "react-router-dom";

// Banner "← Volver a la ficha 360° del cliente" — visible sólo si se llegó desde
// la Visión 360 (query param ?volver=<cliente_id>).
export default function VolverFicha() {
  const [p] = useSearchParams();
  const v = p.get("volver");
  if (!v) return null;
  return (
    <Link to={`/clientes/vision-360?cliente=${v}`}
      style={{
        display: "inline-flex", alignItems: "center", gap: 6, marginBottom: 12,
        fontSize: 13, fontWeight: 600, padding: "7px 12px", borderRadius: 8,
        border: "1px solid var(--border)", background: "var(--accent-soft)", color: "var(--brand)",
      }}>
      ← Volver a la ficha 360° del cliente
    </Link>
  );
}
