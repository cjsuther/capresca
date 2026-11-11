import { useState } from "react";
import { Download, Copy, Check } from "lucide-react";

/** Los 10 códigos de recuperación: se muestran UNA sola vez, para descargar, copiar o imprimir. */
export function CodigosRecuperacion({ codigos, usuario = "" }) {
  const [copiado, setCopiado] = useState(false);
  const texto = [
    "Portezuelo — códigos de recuperación del doble factor",
    usuario ? `Usuario: ${usuario}` : null,
    `Generados: ${new Date().toLocaleString("es-AR")}`,
    "",
    "Cada código sirve UNA sola vez, si no tenés el celular a mano.",
    "Guardalos en un lugar seguro (no en el mismo celular).",
    "",
    ...codigos,
    "",
  ].filter((l) => l !== null).join("\n");

  const descargar = () => {
    const url = URL.createObjectURL(new Blob([texto], { type: "text/plain;charset=utf-8" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `portezuelo-codigos-recuperacion${usuario ? `-${usuario}` : ""}.txt`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  const copiar = async () => {
    try {
      await navigator.clipboard.writeText(codigos.join("\n"));
      setCopiado(true);
    } catch {
      setCopiado(false);
    }
  };

  if (!codigos?.length) {
    return (
      <p className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
        No se pudieron generar los códigos de recuperación. Generalos desde tu menú → Doble factor.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-gray-600">
        Guardá estos códigos: <strong>se muestran una sola vez</strong>. Cada uno sirve para entrar una vez si
        perdés el celular.
      </p>
      <ul aria-label="Códigos de recuperación" className="grid grid-cols-2 gap-2 font-mono text-sm bg-gray-50 border rounded-lg p-3">
        {codigos.map((c) => <li key={c} className="text-center">{c}</li>)}
      </ul>
      <div className="flex gap-2">
        <button type="button" onClick={descargar}
                className="flex items-center gap-1.5 px-3 py-2 text-sm border rounded-lg hover:bg-gray-50">
          <Download size={14} /> Descargar
        </button>
        <button type="button" onClick={copiar}
                className="flex items-center gap-1.5 px-3 py-2 text-sm border rounded-lg hover:bg-gray-50">
          {copiado ? <Check size={14} /> : <Copy size={14} />} {copiado ? "Copiados" : "Copiar"}
        </button>
      </div>
    </div>
  );
}
