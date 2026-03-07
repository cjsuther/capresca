import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getClients } from "../../../api/clientes";
import { Search, User, Building2 } from "lucide-react";

export default function ClientesListPage() {
  const navigate = useNavigate();
  const [data, setData] = useState({ data: [], total: 0 });
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("");

  const load = (params = {}) => {
    setLoading(true);
    getClients({ search, client_type: typeFilter, ...params })
      .then(setData)
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const handleSearch = (e) => {
    e.preventDefault();
    load();
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold text-gray-800">Clientes</h2>
        <span className="text-sm text-gray-500">{data.total} registros</span>
      </div>

      <form onSubmit={handleSearch} className="flex gap-3 mb-6">
        <div className="relative flex-1">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            className="input w-full pl-9"
            placeholder="Buscar por nombre, documento, email..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <select className="input w-40" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
          <option value="">Todos</option>
          <option value="HUMAN">Persona Física</option>
          <option value="LEGAL">Persona Jurídica</option>
        </select>
        <button type="submit" className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">Buscar</button>
      </form>

      <div className="bg-white border rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-gray-600">
            <tr>
              <th className="text-left px-4 py-3 font-medium">Tipo</th>
              <th className="text-left px-4 py-3 font-medium">Código</th>
              <th className="text-left px-4 py-3 font-medium">Nombre</th>
              <th className="text-left px-4 py-3 font-medium">Email</th>
              <th className="text-left px-4 py-3 font-medium">Ciudad</th>
              <th className="text-left px-4 py-3 font-medium">Estado</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400">Cargando...</td></tr>
            ) : data.data.length === 0 ? (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400">Sin resultados</td></tr>
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
    </div>
  );
}
