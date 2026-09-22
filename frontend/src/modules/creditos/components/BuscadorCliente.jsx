import { useEffect, useRef, useState } from "react";
import { Search, X } from "lucide-react";
import { searchClients } from "../../../api/clientes";

/** Nombre visible de un cliente del padrón (persona física o jurídica). */
export function nombreCliente(c) {
  if (!c) return "";
  if (c.human_profile) return `${c.human_profile.last_name}, ${c.human_profile.first_name}`.replace(/^, |, $/, "");
  if (c.legal_profile) return c.legal_profile.legal_name;
  return c.code;
}

const documentoCliente = (c) =>
  c?.human_profile?.document_number || c?.legal_profile?.tax_id || "";

/**
 * Buscador de clientes contra el PADRÓN del sistema (módulo Clientes). Créditos no tiene maestro
 * propio: las pantallas eligen acá y trabajan con el id del padrón.
 *
 * onSelect(cliente) recibe el cliente elegido (o null al limpiar).
 */
export function BuscadorCliente({ onSelect, seleccionado, placeholder = "Buscar cliente por nombre o documento", autoFocus }) {
  const [q, setQ] = useState("");
  const [resultados, setResultados] = useState([]);
  const [abierto, setAbierto] = useState(false);
  const [buscando, setBuscando] = useState(false);
  const [error, setError] = useState("");
  const caja = useRef(null);

  useEffect(() => {
    if (!q.trim() || q.trim().length < 2) { setResultados([]); return; }
    const t = setTimeout(async () => {
      setBuscando(true); setError("");
      try {
        const d = await searchClients(q.trim());
        setResultados(d.data || []);
        setAbierto(true);
      } catch (e) {
        setError(e.response?.data?.detail || "No se pudo consultar el padrón de clientes");
        setResultados([]);
        setAbierto(true);
      } finally { setBuscando(false); }
    }, 300);                                   // debounce: no dispara una búsqueda por tecla
    return () => clearTimeout(t);
  }, [q]);

  useEffect(() => {
    const cerrar = (e) => { if (caja.current && !caja.current.contains(e.target)) setAbierto(false); };
    window.addEventListener("click", cerrar);
    return () => window.removeEventListener("click", cerrar);
  }, []);

  if (seleccionado) {
    return (
      <div className="flex items-center gap-2 border border-gray-300 rounded-lg px-3 py-2 bg-surface text-sm">
        <span className="font-medium text-gray-800">{nombreCliente(seleccionado)}</span>
        {documentoCliente(seleccionado) && (
          <span className="text-gray-400">· {documentoCliente(seleccionado)}</span>
        )}
        <button
          type="button"
          aria-label="Cambiar cliente"
          onClick={() => { onSelect(null); setQ(""); setResultados([]); }}
          className="ml-auto p-0.5 text-gray-400 hover:text-gray-700"
        ><X size={15} /></button>
      </div>
    );
  }

  return (
    <div className="relative" ref={caja}>
      <div className="relative">
        <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
        <input
          className="input w-full pl-8"
          value={q}
          autoFocus={autoFocus}
          placeholder={placeholder}
          onChange={(e) => setQ(e.target.value)}
          onFocus={() => resultados.length && setAbierto(true)}
        />
      </div>
      {abierto && (resultados.length > 0 || buscando || error) && (
        <div className="absolute z-30 mt-1 w-full bg-surface border rounded-xl shadow-lg max-h-72 overflow-y-auto">
          {buscando && <p className="px-3 py-2 text-sm text-gray-400">Buscando…</p>}
          {error && <p className="px-3 py-2 text-sm text-red-600">{error}</p>}
          {!buscando && !error && !resultados.length && (
            <p className="px-3 py-2 text-sm text-gray-400">Sin coincidencias en el padrón.</p>
          )}
          {resultados.map((c) => (
            <button
              key={c.id}
              type="button"
              onClick={() => { onSelect(c); setAbierto(false); }}
              className="w-full text-left px-3 py-2 text-sm hover:bg-gray-50"
            >
              <span className="text-gray-800">{nombreCliente(c)}</span>
              {documentoCliente(c) && <span className="text-gray-400"> · {documentoCliente(c)}</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
