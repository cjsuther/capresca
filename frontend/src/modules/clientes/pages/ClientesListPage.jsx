import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getClients } from "../../../api/clientes";
import { Search, User, Building2, ChevronLeft, ChevronRight } from "lucide-react";

const num = (n) => Number(n || 0).toLocaleString("es-AR");

export default function ClientesListPage() {
  const navigate = useNavigate();
  const [data, setData] = useState({ data: [], total: 0 });
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  // El padrón son decenas de miles de clientes: la lista se pide de a una página al servidor.
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(20);
  const [buscado, setBuscado] = useState(0);   // sube al apretar Buscar; dispara la recarga

  useEffect(() => {
    let vigente = true;
    setLoading(true);
    getClients({ search, client_type: typeFilter, page, per_page: perPage })
      .then((d) => { if (vigente) setData(d); })
      .finally(() => { if (vigente) setLoading(false); });
    return () => { vigente = false; };   // una búsqueda vieja no pisa el resultado de la nueva
  }, [page, perPage, buscado]);          // eslint-disable-line react-hooks/exhaustive-deps

  const handleSearch = (e) => {
    e.preventDefault();
    setPage(1);                          // una búsqueda nueva arranca en la primera página
    setBuscado((n) => n + 1);
  };

  const paginas = Math.max(1, Math.ceil(data.total / perPage));
  const desde = data.total === 0 ? 0 : (page - 1) * perPage + 1;
  const hasta = Math.min(page * perPage, data.total);

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <h2 className="text-xl font-semibold text-gray-800">Clientes</h2>
        <span className="text-sm text-gray-500">{num(data.total)} registros</span>
      </div>

      <form onSubmit={handleSearch} className="flex flex-wrap gap-3 mb-6">
        <div className="relative flex-1 min-w-[200px]">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            className="input w-full pl-9"
            placeholder="Buscar por nombre, documento, email..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <select className="input w-full sm:w-40" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
          <option value="">Todos</option>
          <option value="HUMAN">Persona Física</option>
          <option value="LEGAL">Persona Jurídica</option>
        </select>
        <button type="submit" className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">Buscar</button>
      </form>

      <div className="bg-surface border rounded-xl overflow-x-auto">
        <table className="w-full text-sm min-w-[520px]">
          <thead className="bg-gray-50 text-gray-600">
            <tr>
              <th className="text-left px-4 py-3 font-medium">Tipo</th>
              <th className="text-left px-4 py-3 font-medium">Código</th>
              <th className="text-left px-4 py-3 font-medium">Nombre</th>
              <th className="text-left px-4 py-3 font-medium">Nro. Agencia</th>
              <th className="text-left px-4 py-3 font-medium">Email</th>
              <th className="text-left px-4 py-3 font-medium">Ciudad</th>
              <th className="text-left px-4 py-3 font-medium">Estado</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400">Cargando...</td></tr>
            ) : data.data.length === 0 ? (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400">Sin resultados</td></tr>
            ) : data.data.map((client) => {
              const name = client.human_profile
                ? `${client.human_profile.first_name} ${client.human_profile.last_name}`
                : client.legal_profile?.legal_name || "—";

              return (
                <tr
                  key={client.id}
                  onClick={() => navigate(`/modules/clientes/${client.id}`)}
                  className="hover:bg-blue-50 cursor-pointer"
                >
                  <td className="px-4 py-3">
                    {client.client_type === "HUMAN"
                      ? <User size={16} className="text-blue-500" />
                      : <Building2 size={16} className="text-purple-500" />
                    }
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-gray-500">{client.code}</td>
                  <td className="px-4 py-3 font-medium">{name}</td>
                  <td className="px-4 py-3 font-mono text-xs text-gray-600">{client.legal_profile?.agency_number || "—"}</td>
                  <td className="px-4 py-3 text-gray-600">{client.email || "—"}</td>
                  <td className="px-4 py-3 text-gray-600">{client.city || "—"}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${client.is_active ? "bg-green-100 text-green-700" : "bg-red-100 text-red-600"}`}>
                      {client.is_active ? "Activo" : "Inactivo"}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 mt-4">
        <p className="text-sm text-gray-500 tabular-nums">
          {data.total === 0 ? "Sin resultados" : `${num(desde)}–${num(hasta)} de ${num(data.total)}`}
        </p>

        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-gray-500">
            Por página
            <select className="input py-1" value={perPage} aria-label="Clientes por página"
                    onChange={(e) => { setPerPage(Number(e.target.value)); setPage(1); }}>
              {[20, 50, 100].map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          </label>

          <div className="flex items-center gap-1">
            <button type="button" aria-label="Página anterior" disabled={page <= 1 || loading}
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    className="p-2 rounded-lg border border-gray-300 text-gray-600 enabled:hover:bg-gray-50 disabled:opacity-40">
              <ChevronLeft size={16} />
            </button>
            <span className="text-sm text-gray-600 tabular-nums px-2">
              {num(page)} de {num(paginas)}
            </span>
            <button type="button" aria-label="Página siguiente" disabled={page >= paginas || loading}
                    onClick={() => setPage((p) => Math.min(paginas, p + 1))}
                    className="p-2 rounded-lg border border-gray-300 text-gray-600 enabled:hover:bg-gray-50 disabled:opacity-40">
              <ChevronRight size={16} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
