const TONOS = {
  ok: "bg-green-100 text-green-700",
  warn: "bg-yellow-100 text-yellow-700",
  crit: "bg-red-100 text-red-600",
  brand: "bg-blue-100 text-blue-700",
  neutral: "bg-gray-100 text-gray-500",
};

/** Etiqueta de estado. `tono`: ok | warn | crit | brand | neutral. */
export function Pill({ tono = "neutral", children }) {
  return (
    <span className={`inline-block text-xs px-2 py-0.5 rounded-full whitespace-nowrap ${TONOS[tono] || TONOS.neutral}`}>
      {children}
    </span>
  );
}
