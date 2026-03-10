import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  getClient, getNotes, addNote,
  updateClient, updateHumanProfile, updateLegalProfile,
  getMembers, addMember, removeMember,
  searchClients, getCbus, addCbu, deleteCbu,
} from "../../../api/clientes";
import { PermissionGate } from "../../../components/PrivateRoute";
import {
  ArrowLeft, User, Building2, Pencil, Check, X,
  UserPlus, Trash2, Search, CreditCard, Plus,
} from "lucide-react";

// ── Campo editable ───────────────────────────────────────────────
function Field({ label, value, editing, name, form, onChange, type = "text" }) {
  return (
    <div className="flex justify-between items-center text-sm">
      <dt className="text-gray-500">{label}</dt>
      <dd>
        {editing
          ? <input
              type={type}
              className="input text-sm text-right w-44"
              value={form[name] ?? ""}
              onChange={(e) => onChange(name, e.target.value)}
            />
          : (value || "—")
        }
      </dd>
    </div>
  );
}

export default function ClienteDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [client, setClient] = useState(null);
  const [notes, setNotes] = useState([]);
  const [noteText, setNoteText] = useState("");
  const [error, setError] = useState("");

  // Edición datos base
  const [editingBase, setEditingBase] = useState(false);
  const [baseForm, setBaseForm] = useState({});

  // Edición perfil
  const [editingProfile, setEditingProfile] = useState(false);
  const [profileForm, setProfileForm] = useState({});

  // Miembros (solo PJ)
  const [members, setMembers] = useState([]);
  const [memberSearch, setMemberSearch] = useState("");
  const [memberSearchResults, setMemberSearchResults] = useState([]);
  const [memberRole, setMemberRole] = useState("");
  const [selectedHuman, setSelectedHuman] = useState(null);
  const [searchLoading, setSearchLoading] = useState(false);

  // CBUs
  const [cbus, setCbus] = useState([]);
  const [newCbu, setNewCbu] = useState("");
  const [newCbuAlias, setNewCbuAlias] = useState("");
  const [cbuError, setCbuError] = useState("");

  const load = () =>
    getClient(id).then((c) => {
      setClient(c);
      setBaseForm({ email: c.email || "", phone: c.phone || "", address: c.address || "", city: c.city || "", country: c.country || "" });
      const p = c.client_type === "HUMAN" ? c.human_profile : c.legal_profile;
      setProfileForm(p ? { ...p } : {});
    });

  const loadMembers = () => getMembers(id).then(setMembers);

  useEffect(() => {
    load();
    getNotes(id).then(setNotes);
  }, [id]);

  const loadCbus = () => getCbus(id).then(setCbus);

  useEffect(() => {
    if (client?.client_type === "LEGAL") {
      loadMembers();
      loadCbus();
    }
  }, [client]);

  const handleAddCbu = async (e) => {
    e.preventDefault();
    setCbuError("");
    if (!/^\d{22}$/.test(newCbu)) { setCbuError("El CBU debe tener exactamente 22 dígitos"); return; }
    try {
      await addCbu(id, { cbu: newCbu, alias: newCbuAlias || null });
      setNewCbu("");
      setNewCbuAlias("");
      loadCbus();
    } catch (err) {
      setCbuError(err.response?.data?.detail || "Error al agregar CBU");
    }
  };

  const handleDeleteCbu = async (cbuId) => {
    if (!confirm("¿Eliminar este CBU?")) return;
    try {
      await deleteCbu(id, cbuId);
      loadCbus();
    } catch (err) {
      setError(err.response?.data?.detail || "Error al eliminar CBU");
    }
  };

  const handleAddNote = async (e) => {
    e.preventDefault();
    if (!noteText.trim()) return;
    await addNote(id, noteText);
    setNoteText("");
    getNotes(id).then(setNotes);
  };

  // ── Guardar datos base ───────────────────────────────────────
  const handleSaveBase = async () => {
    setError("");
    try {
      await updateClient(id, baseForm);
      setEditingBase(false);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || "Error al guardar");
    }
  };

  // ── Guardar perfil ───────────────────────────────────────────
  const handleSaveProfile = async () => {
    setError("");
    try {
      if (client.client_type === "HUMAN") {
        await updateHumanProfile(id, profileForm);
      } else {
        await updateLegalProfile(id, profileForm);
      }
      setEditingProfile(false);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || "Error al guardar");
    }
  };

  // ── Buscar personas físicas ──────────────────────────────────
  const handleMemberSearch = async (val) => {
    setMemberSearch(val);
    setSelectedHuman(null);
    if (val.length < 2) { setMemberSearchResults([]); return; }
    setSearchLoading(true);
    try {
      const res = await searchClients(val);
      setMemberSearchResults(res.data.filter((c) => c.client_type === "HUMAN"));
    } finally {
      setSearchLoading(false);
    }
  };

  const handleAddMember = async () => {
    if (!selectedHuman) return;
    setError("");
    try {
      await addMember(id, { human_client_id: selectedHuman.id, role: memberRole || null });
      setSelectedHuman(null);
      setMemberSearch("");
      setMemberSearchResults([]);
      setMemberRole("");
      loadMembers();
    } catch (err) {
      setError(err.response?.data?.detail || "Error al agregar miembro");
    }
  };

  const handleRemoveMember = async (memberId) => {
    if (!confirm("¿Quitar este miembro?")) return;
    setError("");
    try {
      await removeMember(id, memberId);
      loadMembers();
    } catch (err) {
      setError(err.response?.data?.detail || "Error al quitar miembro");
    }
  };

  if (!client) return <p className="text-gray-400 text-sm">Cargando...</p>;

  const isHuman = client.client_type === "HUMAN";
  const profile = isHuman ? client.human_profile : client.legal_profile;
  const displayName = isHuman
    ? `${profile?.first_name} ${profile?.last_name}`
    : profile?.legal_name;

  const setBase = (k, v) => setBaseForm((f) => ({ ...f, [k]: v }));
  const setProf = (k, v) => setProfileForm((f) => ({ ...f, [k]: v }));

  return (
    <div className="max-w-4xl">
      <button onClick={() => navigate(-1)} className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 mb-6">
        <ArrowLeft size={16} /> Volver
      </button>

      <div className="flex items-center gap-3 mb-6">
        {isHuman ? <User size={28} className="text-blue-500" /> : <Building2 size={28} className="text-purple-500" />}
        <div>
          <h2 className="text-xl font-semibold text-gray-800">{displayName}</h2>
          <span className="text-xs font-mono text-gray-400">{client.code}</span>
        </div>
        <span className={`ml-auto text-xs px-2 py-1 rounded-full ${client.is_active ? "bg-green-100 text-green-700" : "bg-red-100 text-red-600"}`}>
          {client.is_active ? "Activo" : "Inactivo"}
        </span>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-2 text-sm mb-4">{error}</div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        {/* Datos base */}
        <div className="bg-white border rounded-xl p-5">
          <div className="flex justify-between items-center mb-3">
            <h3 className="font-medium text-gray-700">Datos generales</h3>
            <PermissionGate moduleCode="clientes" action="clients:write">
              {editingBase ? (
                <div className="flex gap-1">
                  <button onClick={handleSaveBase} className="flex items-center gap-1 px-2 py-1 text-xs bg-green-600 text-white rounded-lg hover:bg-green-700">
                    <Check size={12} /> Guardar
                  </button>
                  <button onClick={() => { setEditingBase(false); load(); }} className="p-1 text-gray-400 hover:text-gray-600 border rounded-lg">
                    <X size={14} />
                  </button>
                </div>
              ) : (
                <button onClick={() => setEditingBase(true)} className="p-1.5 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg">
                  <Pencil size={14} />
                </button>
              )}
            </PermissionGate>
          </div>
          <dl className="space-y-2">
            <Field label="Email"     value={client.email}   editing={editingBase} name="email"   form={baseForm} onChange={setBase} />
            <Field label="Teléfono"  value={client.phone}   editing={editingBase} name="phone"   form={baseForm} onChange={setBase} />
            <Field label="Dirección" value={client.address} editing={editingBase} name="address" form={baseForm} onChange={setBase} />
            <Field label="Ciudad"    value={client.city}    editing={editingBase} name="city"    form={baseForm} onChange={setBase} />
            <Field label="País"      value={client.country} editing={editingBase} name="country" form={baseForm} onChange={setBase} />
          </dl>
        </div>

        {/* Perfil */}
        <div className="bg-white border rounded-xl p-5">
          <div className="flex justify-between items-center mb-3">
            <h3 className="font-medium text-gray-700">{isHuman ? "Datos personales" : "Datos de la empresa"}</h3>
            <PermissionGate moduleCode="clientes" action="clients:write">
              {editingProfile ? (
                <div className="flex gap-1">
                  <button onClick={handleSaveProfile} className="flex items-center gap-1 px-2 py-1 text-xs bg-green-600 text-white rounded-lg hover:bg-green-700">
                    <Check size={12} /> Guardar
                  </button>
                  <button onClick={() => { setEditingProfile(false); load(); }} className="p-1 text-gray-400 hover:text-gray-600 border rounded-lg">
                    <X size={14} />
                  </button>
                </div>
              ) : (
                <button onClick={() => setEditingProfile(true)} className="p-1.5 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg">
                  <Pencil size={14} />
                </button>
              )}
            </PermissionGate>
          </div>
          {isHuman && (
            <dl className="space-y-2">
              <Field label="Nombre"       value={profile?.first_name}      editing={editingProfile} name="first_name"      form={profileForm} onChange={setProf} />
              <Field label="Apellido"     value={profile?.last_name}       editing={editingProfile} name="last_name"       form={profileForm} onChange={setProf} />
              <Field label="Tipo doc."    value={profile?.document_type}   editing={editingProfile} name="document_type"   form={profileForm} onChange={setProf} />
              <Field label="Nro. doc."    value={profile?.document_number} editing={editingProfile} name="document_number" form={profileForm} onChange={setProf} />
              <Field label="Nacimiento"   value={profile?.birth_date}      editing={editingProfile} name="birth_date"      form={profileForm} onChange={setProf} />
              <Field label="Nacionalidad" value={profile?.nationality}     editing={editingProfile} name="nationality"     form={profileForm} onChange={setProf} />
            </dl>
          )}
          {!isHuman && (
            <dl className="space-y-2">
              <Field label="Razón social"  value={profile?.legal_name}          editing={editingProfile} name="legal_name"          form={profileForm} onChange={setProf} />
              <Field label="Nombre com."   value={profile?.trade_name}          editing={editingProfile} name="trade_name"          form={profileForm} onChange={setProf} />
              <Field label="Tipo ID fiscal" value={profile?.tax_id_type}        editing={editingProfile} name="tax_id_type"         form={profileForm} onChange={setProf} />
              <Field label="ID Fiscal"     value={profile?.tax_id}              editing={editingProfile} name="tax_id"              form={profileForm} onChange={setProf} />
              <Field label="Representante" value={profile?.legal_representative} editing={editingProfile} name="legal_representative" form={profileForm} onChange={setProf} />
              <Field label="Sector"        value={profile?.industry_sector}     editing={editingProfile} name="industry_sector"     form={profileForm} onChange={setProf} />
            </dl>
          )}
        </div>
      </div>

      {/* Miembros (solo PJ) */}
      {!isHuman && (
        <div className="bg-white border rounded-xl p-5 mb-6">
          <h3 className="font-medium text-gray-700 mb-4">Personas físicas vinculadas</h3>

          {/* Agregar miembro */}
          <PermissionGate moduleCode="clientes" action="clients:write">
            <div className="mb-4 p-4 bg-gray-50 rounded-lg">
              <p className="text-xs font-medium text-gray-600 mb-3">Agregar persona física</p>
              <div className="flex gap-2 mb-2 relative">
                <div className="relative flex-1">
                  <Search size={14} className="absolute left-3 top-2.5 text-gray-400" />
                  <input
                    className="input w-full pl-8 text-sm"
                    placeholder="Buscar por nombre o documento..."
                    value={selectedHuman ? `${selectedHuman.human_profile?.first_name} ${selectedHuman.human_profile?.last_name}` : memberSearch}
                    onChange={(e) => { handleMemberSearch(e.target.value); }}
                  />
                  {memberSearchResults.length > 0 && !selectedHuman && (
                    <div className="absolute z-10 top-full mt-1 w-full bg-white border rounded-lg shadow-lg max-h-48 overflow-y-auto">
                      {memberSearchResults.map((c) => (
                        <button
                          key={c.id}
                          onClick={() => { setSelectedHuman(c); setMemberSearchResults([]); setMemberSearch(""); }}
                          className="w-full text-left px-3 py-2 text-sm hover:bg-blue-50 border-b last:border-b-0"
                        >
                          <span className="font-medium">{c.human_profile?.first_name} {c.human_profile?.last_name}</span>
                          <span className="text-gray-400 text-xs ml-2">{c.human_profile?.document_number || c.code}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                <input
                  className="input text-sm w-36"
                  placeholder="Rol (opcional)"
                  value={memberRole}
                  onChange={(e) => setMemberRole(e.target.value)}
                />
                <button
                  onClick={handleAddMember}
                  disabled={!selectedHuman}
                  className="flex items-center gap-1 px-3 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-40"
                >
                  <UserPlus size={14} /> Agregar
                </button>
                {selectedHuman && (
                  <button onClick={() => { setSelectedHuman(null); setMemberSearch(""); }} className="p-2 text-gray-400 hover:text-gray-600 border rounded-lg">
                    <X size={14} />
                  </button>
                )}
              </div>
            </div>
          </PermissionGate>

          {/* Lista de miembros */}
          {members.length === 0 ? (
            <p className="text-sm text-gray-400">Sin personas físicas vinculadas</p>
          ) : (
            <div className="space-y-2">
              {members.map((m) => {
                const p = m.human_client?.human_profile;
                return (
                  <div key={m.id} className="flex items-center justify-between bg-gray-50 rounded-lg px-4 py-3">
                    <div className="flex items-center gap-3">
                      <User size={16} className="text-blue-400" />
                      <div>
                        <span className="text-sm font-medium text-gray-800">
                          {p?.first_name} {p?.last_name}
                        </span>
                        {p?.document_number && (
                          <span className="text-xs text-gray-400 ml-2">{p.document_type} {p.document_number}</span>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      {m.role && (
                        <span className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded">{m.role}</span>
                      )}
                      <PermissionGate moduleCode="clientes" action="clients:write">
                        <button
                          onClick={() => handleRemoveMember(m.id)}
                          className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg"
                        >
                          <Trash2 size={14} />
                        </button>
                      </PermissionGate>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* CBUs (solo PJ) */}
      {!isHuman && (
        <div className="bg-white border rounded-xl p-5 mb-6">
          <div className="flex items-center gap-2 mb-4">
            <CreditCard size={16} className="text-gray-500" />
            <h3 className="font-medium text-gray-700">CBUs registrados</h3>
          </div>

          <PermissionGate moduleCode="clientes" action="clients:write">
            <form onSubmit={handleAddCbu} className="flex gap-2 mb-4">
              <input
                className="input text-sm w-52 font-mono"
                placeholder="CBU (22 dígitos)"
                value={newCbu}
                maxLength={22}
                onChange={(e) => setNewCbu(e.target.value.replace(/\D/g, ""))}
              />
              <input
                className="input text-sm flex-1"
                placeholder="Alias (opcional)"
                value={newCbuAlias}
                onChange={(e) => setNewCbuAlias(e.target.value)}
              />
              <button type="submit" className="flex items-center gap-1 px-3 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700">
                <Plus size={14} /> Agregar
              </button>
            </form>
            {cbuError && <p className="text-xs text-red-600 mb-3">{cbuError}</p>}
          </PermissionGate>

          {cbus.length === 0 ? (
            <p className="text-sm text-gray-400">Sin CBUs registrados</p>
          ) : (
            <div className="space-y-2">
              {cbus.map((c) => (
                <div key={c.id} className="flex items-center justify-between bg-gray-50 rounded-lg px-4 py-2.5">
                  <div>
                    <span className="text-sm font-mono text-gray-800">{c.cbu}</span>
                    {c.alias && <span className="ml-3 text-xs text-gray-500">{c.alias}</span>}
                  </div>
                  <PermissionGate moduleCode="clientes" action="clients:write">
                    <button
                      onClick={() => handleDeleteCbu(c.id)}
                      className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg"
                    >
                      <Trash2 size={14} />
                    </button>
                  </PermissionGate>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Notas */}
      <div className="bg-white border rounded-xl p-5">
        <h3 className="font-medium text-gray-700 mb-4">Notas</h3>
        <form onSubmit={handleAddNote} className="flex gap-2 mb-4">
          <input
            className="input flex-1 text-sm"
            placeholder="Agregar nota..."
            value={noteText}
            onChange={(e) => setNoteText(e.target.value)}
          />
          <button type="submit" className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700">Agregar</button>
        </form>
        {notes.length === 0 ? (
          <p className="text-sm text-gray-400">Sin notas</p>
        ) : (
          <div className="space-y-3">
            {notes.map((note) => (
              <div key={note.id} className="bg-gray-50 rounded-lg px-4 py-3">
                <p className="text-sm text-gray-700">{note.content}</p>
                <p className="text-xs text-gray-400 mt-1">{new Date(note.created_at).toLocaleString()}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
