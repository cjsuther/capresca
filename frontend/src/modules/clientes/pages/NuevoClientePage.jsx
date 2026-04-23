import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { createHumanClient, createLegalClient } from "../../../api/clientes";

export default function NuevoClientePage() {
  const { type } = useParams();
  const isHuman = type === "humano";
  const navigate = useNavigate();

  const [base, setBase] = useState({ email: "", phone: "", address: "", city: "", country: "AR" });
  const [profile, setProfile] = useState(
    isHuman
      ? { first_name: "", last_name: "", document_type: "DNI", document_number: "", nationality: "" }
      : { legal_name: "", trade_name: "", tax_id: "", tax_id_type: "CUIT", legal_representative: "", industry_sector: "", agency_number: "" }
  );
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    try {
      const payload = { ...base, profile };
      if (isHuman) {
        await createHumanClient(payload);
      } else {
        await createLegalClient(payload);
      }
      navigate("/modules/clientes/lista");
    } catch (err) {
      setError(err.response?.data?.detail || "Error al crear cliente");
    }
  };

  return (
    <div className="max-w-2xl">
      <h2 className="text-xl font-semibold text-gray-800 mb-6">
        {isHuman ? "Nueva Persona Física" : "Nueva Persona Jurídica"}
      </h2>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-2 text-sm mb-4">{error}</div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Datos base */}
        <div className="bg-white border rounded-xl p-6">
          <h3 className="font-medium text-gray-700 mb-4">Datos de contacto</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
              <input type="email" className="input w-full" value={base.email} onChange={(e) => setBase({ ...base, email: e.target.value })} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Teléfono</label>
              <input className="input w-full" value={base.phone} onChange={(e) => setBase({ ...base, phone: e.target.value })} />
            </div>
            <div className="col-span-1 sm:col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-1">Dirección</label>
              <input className="input w-full" value={base.address} onChange={(e) => setBase({ ...base, address: e.target.value })} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Ciudad</label>
              <input className="input w-full" value={base.city} onChange={(e) => setBase({ ...base, city: e.target.value })} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">País</label>
              <input className="input w-full" value={base.country} onChange={(e) => setBase({ ...base, country: e.target.value })} />
            </div>
          </div>
        </div>

        {/* Perfil específico */}
        <div className="bg-white border rounded-xl p-6">
          <h3 className="font-medium text-gray-700 mb-4">
            {isHuman ? "Datos personales" : "Datos de la empresa"}
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {isHuman ? (
              <>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Nombre *</label>
                  <input className="input w-full" value={profile.first_name} onChange={(e) => setProfile({ ...profile, first_name: e.target.value })} required />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Apellido *</label>
                  <input className="input w-full" value={profile.last_name} onChange={(e) => setProfile({ ...profile, last_name: e.target.value })} required />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Tipo de documento</label>
                  <select className="input w-full" value={profile.document_type} onChange={(e) => setProfile({ ...profile, document_type: e.target.value })}>
                    <option>DNI</option><option>PASAPORTE</option><option>CEDULA</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Número de documento</label>
                  <input className="input w-full" value={profile.document_number} onChange={(e) => setProfile({ ...profile, document_number: e.target.value })} />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Nacionalidad</label>
                  <input className="input w-full" value={profile.nationality} onChange={(e) => setProfile({ ...profile, nationality: e.target.value })} />
                </div>
              </>
            ) : (
              <>
                <div className="col-span-1 sm:col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-1">Razón social *</label>
                  <input className="input w-full" value={profile.legal_name} onChange={(e) => setProfile({ ...profile, legal_name: e.target.value })} required />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Nombre comercial</label>
                  <input className="input w-full" value={profile.trade_name} onChange={(e) => setProfile({ ...profile, trade_name: e.target.value })} />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Tipo de identificación fiscal</label>
                  <select className="input w-full" value={profile.tax_id_type} onChange={(e) => setProfile({ ...profile, tax_id_type: e.target.value })}>
                    <option>CUIT</option><option>RUC</option><option>NIT</option><option>RUT</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Número fiscal</label>
                  <input className="input w-full" value={profile.tax_id} onChange={(e) => setProfile({ ...profile, tax_id: e.target.value })} />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Representante legal</label>
                  <input className="input w-full" value={profile.legal_representative} onChange={(e) => setProfile({ ...profile, legal_representative: e.target.value })} />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Sector / industria</label>
                  <input className="input w-full" value={profile.industry_sector} onChange={(e) => setProfile({ ...profile, industry_sector: e.target.value })} />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Nro. Agencia</label>
                  <input className="input w-full" placeholder="Ej: 000001" value={profile.agency_number} onChange={(e) => setProfile({ ...profile, agency_number: e.target.value })} />
                </div>
              </>
            )}
          </div>
        </div>

        <div className="flex gap-3 justify-end">
          <button type="button" onClick={() => navigate(-1)} className="px-5 py-2 text-sm text-gray-600 border rounded-lg hover:bg-gray-50">
            Cancelar
          </button>
          <button type="submit" className="px-5 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700">
            Crear cliente
          </button>
        </div>
      </form>
    </div>
  );
}
