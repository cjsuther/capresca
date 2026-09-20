import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api";
import DataTable, { Col } from "../components/DataTable";
import LimpiarFiltros from "../components/LimpiarFiltros";
import { confirmar, avisar, pedirTexto } from "../ui/dialog";

const money = (v: any) =>
  v == null ? "—" : Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });
const num = (v: any) => (v == null ? "—" : Number(v).toLocaleString("es-AR"));
const fmtCuil = (c: string) => (c && c.length === 11 ? `${c.slice(0, 2)}-${c.slice(2, 10)}-${c.slice(10)}` : c || "—");
const LIMIT = 25;

// Dígito verificador del CUIL (mismo algoritmo que el backend `valida_cuil`, para no desajustar front↔back).
function cuilValido(cuil: string): boolean {
  const c = (cuil || "").replace(/\D/g, "");
  if (c.length !== 11) return false;
  const mult = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2];
  const suma = mult.reduce((a, m, i) => a + Number(c[i]) * m, 0);
  let verif = 11 - (suma % 11);
  if (verif === 11) verif = 0; else if (verif === 10) verif = 9;
  return verif === Number(c[10]);
}
const emailValido = (e: string) => !e || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e);

const VACIO = {
  id: 0, id_cliente: "", cuil: "", dni: "", apellido_nombre: "", sexo: "", fecha_nacimiento: "",
  domicilio: "", barrio: "", localidad: "", telefono: "", email: "", cbu: "", debito_automatico: false,
  sueldo: "", categoria_funcion: "", fecha_ingreso: "", tipo_cliente: 0, organismo_id: "" as any, baja: false,
};

export default function Clientes() {
  const nav = useNavigate();
  const [data, setData] = useState<any>({ items: [], total: 0 });
  const [q, setQ] = useState("");
  const [busq, setBusq] = useState("");
  const [estado, setEstado] = useState("activos");
  const [orgFiltro, setOrgFiltro] = useState("");
  const [offset, setOffset] = useState(0);
  const [organismos, setOrganismos] = useState<any[]>([]);
  const [sort, setSort] = useState("apellido_nombre");
  const [order, setOrder] = useState<"asc" | "desc">("asc");

  const [form, setForm] = useState<any>(null);   // cliente en edición/alta (null = drawer cerrado)
  const [esAlta, setEsAlta] = useState(false);
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [params, setParams] = useSearchParams();
  // Si venimos desde una solicitud express (Solicitudes → "Dar de alta en maestro"): al guardar volvemos a vincular.
  const [desdeSolicitud, setDesdeSolicitud] = useState<string>("");

  async function cargar(off = 0, s = sort, o = order) {
    setOffset(off);
    setData(await api.clientes({ q, estado, organismo_id: orgFiltro ? Number(orgFiltro) : undefined, sort: s, order: o, limit: LIMIT, offset: off }));
  }
  useEffect(() => { cargar(0); }, [q, estado, orgFiltro]); // eslint-disable-line
  useEffect(() => { api.adminOrganismos().then(setOrganismos).catch(() => {}); }, []);

  const orgNombre = (id: number) => organismos.find((o) => o.id === id)?.nombre || (id ? `Org. ${id}` : "—");
  const hayFiltros = !!q || !!orgFiltro || estado !== "activos";
  function limpiarFiltros() { setBusq(""); setQ(""); setOrgFiltro(""); setEstado("activos"); }
  function ordenar(k: string) {
    const o = sort === k && order === "asc" ? "desc" : "asc";
    setSort(k); setOrder(o); cargar(0, k, o);
  }

  const cols: Col[] = [
    { key: "id_cliente", label: "ID", sortable: true, render: (c) => c.id_cliente || c.id },
    { key: "apellido_nombre", label: "Apellido y nombre", sortable: true, render: (c) => <b>{c.apellido_nombre}</b> },
    { key: "cuil", label: "CUIL", sortable: true, render: (c) => <span className="num">{fmtCuil(c.cuil)}</span> },
    { key: "dni", label: "DNI", render: (c) => <span className="num">{c.dni || "—"}</span> },
    { key: "organismo", label: "Organismo", render: (c) => orgNombre(c.organismo_id) },
    { key: "sueldo", label: "Sueldo", sortable: true, align: "right", render: (c) => <span className="num">{money(c.sueldo)}</span> },
    { key: "estado", label: "Estado", render: (c) => <span className={`pill ${c.baja ? "crit" : "ok"}`}>{c.baja ? "Baja" : "Activo"}</span> },
  ];
  const acciones = (c: any) => [
    { label: "Editar", icon: "edit", onClick: () => abrirEdicion(c), hidden: c.baja },
    { label: "Ver 360°", icon: "eye", onClick: () => nav(`/clientes/vision-360?cliente=${c.id}`) },
    { label: "Dar de baja", icon: "ban", danger: true, onClick: () => darBaja(c), hidden: c.baja },
    { label: "Reactivar", icon: "rotate-ccw", onClick: () => reactivar(c), hidden: !c.baja },
  ];

  function abrirAlta(prefill: Partial<typeof VACIO> = {}) { setForm({ ...VACIO, ...prefill }); setEsAlta(true); setError(""); }
  // Deep-link desde Solicitudes: abre el alta COMPLETA con los datos declarados precargados.
  useEffect(() => {
    if (params.get("alta") !== "1") return;
    abrirAlta({
      apellido_nombre: params.get("nombre") || "", dni: (params.get("dni") || "").replace(/\D/g, "").slice(0, 9),
      cuil: (params.get("cuil") || "").replace(/\D/g, "").slice(0, 11),
    });
    setDesdeSolicitud(params.get("sid") || "");
    setParams({}, { replace: true });   // limpia la URL; conservamos el sid en estado
  }, [params]);   // eslint-disable-line
  function abrirEdicion(c: any) {
    setForm({
      ...VACIO, ...c,
      fecha_nacimiento: c.fecha_nacimiento || "", fecha_ingreso: c.fecha_ingreso || "",
      sueldo: c.sueldo ?? "", organismo_id: c.organismo_id ?? "",
    });
    setEsAlta(false); setError("");
  }
  function set(k: string, v: any) { setForm((f: any) => ({ ...f, [k]: v })); }

  // Esc cierra la ventana flotante de alta/edición.
  useEffect(() => {
    if (!form) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setForm(null); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [form]);

  // Validaciones del formulario (H-145). El CUIL se valida por dígito verificador (no sólo longitud).
  const cuilInvalido = esAlta && form && !cuilValido(form.cuil);
  const dniDigits = form ? (form.dni || "").replace(/\D/g, "") : "";
  const dniInvalido = !!dniDigits && (dniDigits.length < 7 || dniDigits.length > 8);
  const cbuDigits = form ? (form.cbu || "").replace(/\D/g, "") : "";
  const cbuInvalido = !!cbuDigits && cbuDigits.length !== 22;
  const emailInvalido = form ? !emailValido(form.email || "") : false;
  const sueldoInvalido = form ? (form.sueldo !== "" && !(Number(form.sueldo) >= 0)) : false;
  const puedeGuardar = form && !!(form.apellido_nombre || "").trim()
    && !cuilInvalido && !dniInvalido && !cbuInvalido && !emailInvalido && !sueldoInvalido;

  async function guardar() {
    setError(""); setGuardando(true);
    const payload: any = {
      apellido_nombre: form.apellido_nombre, dni: form.dni, sexo: form.sexo,
      fecha_nacimiento: form.fecha_nacimiento || null, domicilio: form.domicilio, barrio: form.barrio,
      localidad: form.localidad, telefono: form.telefono, email: form.email, cbu: form.cbu,
      debito_automatico: !!form.debito_automatico, sueldo: form.sueldo === "" ? 0 : Number(form.sueldo),
      categoria_funcion: form.categoria_funcion, fecha_ingreso: form.fecha_ingreso || null,
      tipo_cliente: Number(form.tipo_cliente) || 0, organismo_id: form.organismo_id ? Number(form.organismo_id) : null,
    };
    try {
      if (esAlta) {
        const creado = await api.crearCliente({ ...payload, cuil: form.cuil.replace(/\D/g, ""), id_cliente: form.id_cliente });
        setForm(null);
        if (desdeSolicitud) {   // volver a la solicitud y vincular el cliente recién creado
          const sid = desdeSolicitud; setDesdeSolicitud("");
          nav(`/creditos/solicitudes-credito?vincular=${encodeURIComponent(sid)}&cliente=${creado.id}`);
          return;
        }
      } else {
        await api.editarCliente(form.id, payload);
        setForm(null);
      }
      cargar(offset);
    } catch (e: any) { setError(e.message); }
    finally { setGuardando(false); }
  }

  async function darBaja(c: any) {
    const motivo = await pedirTexto({ titulo: "Dar de baja", mensaje: `Dar de baja a ${c.apellido_nombre}. Motivo:`, requerido: true });
    if (!motivo?.trim()) return;
    try { await api.bajaCliente(c.id, motivo.trim()); cargar(offset); }
    catch (e: any) { avisar({ tipo: "error", mensaje: e.message }); }
  }
  async function reactivar(c: any) {
    if (!(await confirmar({ titulo: "Reactivar cliente", mensaje: `¿Reactivar a ${c.apellido_nombre}?` }))) return;
    try { await api.reactivarCliente(c.id); cargar(offset); }
    catch (e: any) { avisar({ tipo: "error", mensaje: e.message }); }
  }

  return (
    <>
      <div style={{ display: "flex", alignItems: "flex-end", gap: 14, flexWrap: "wrap", marginBottom: 16 }}>
        <div>
          <h1 style={{ margin: 0 }}>Maestro de clientes</h1>
          <p className="muted" style={{ margin: 0 }}>{num(data.total)} agentes · alta, baja y modificación</p>
        </div>
        <div style={{ flex: 1 }} />
        <button onClick={() => abrirAlta()}>＋ Nuevo cliente</button>
      </div>

      <div className="card" style={{ padding: 0 }}>
        <div style={{ display: "flex", gap: 10, padding: "12px 14px", borderBottom: "1px solid var(--border)", flexWrap: "wrap" }}>
          <form onSubmit={(e) => { e.preventDefault(); setQ(busq); }} style={{ flex: 1, minWidth: 200, margin: 0 }}>
            <input value={busq} onChange={(e) => setBusq(e.target.value)} placeholder="Buscar por CUIL, DNI o apellido y nombre…" style={{ marginBottom: 0 }} />
          </form>
          <select value={orgFiltro} onChange={(e) => setOrgFiltro(e.target.value)} style={{ marginBottom: 0, maxWidth: 220 }}>
            <option value="">Todos los organismos</option>
            {organismos.map((o) => <option key={o.id} value={o.id}>{o.nombre}</option>)}
          </select>
          <select value={estado} onChange={(e) => setEstado(e.target.value)} style={{ marginBottom: 0, maxWidth: 160 }}>
            <option value="activos">Activos</option>
            <option value="baja">Dados de baja</option>
            <option value="todos">Todos</option>
          </select>
          <LimpiarFiltros activo={hayFiltros} onClear={limpiarFiltros} />
        </div>

        <div style={{ padding: "4px 14px 14px" }}>
          <DataTable columns={cols} rows={data.items} rowKey={(c) => c.id}
                     actions={acciones}
                     total={data.total} limit={LIMIT} offset={offset}
                     sort={sort} order={order} onSort={ordenar} onPage={(off) => cargar(off)}
                     emptyText="Sin clientes para el filtro." />
        </div>
      </div>

      {form && (
        <>
          <div className="drawer-scrim" onClick={() => setForm(null)} />
          <aside className="drawer">
            <div className="dh">
              <div>
                <div className="eyebrow">{esAlta ? "Nuevo cliente" : `Editar cliente · ID ${form.id_cliente || form.id}`}</div>
                <h2>{esAlta ? "Alta de cliente" : form.apellido_nombre}</h2>
              </div>
              <button className="x" onClick={() => setForm(null)}>✕</button>
            </div>
            <div className="dbody">
              {esAlta && desdeSolicitud && <p className="hint" style={{ background: "var(--surface-2)", border: "1px solid var(--border)", borderRadius: 8, padding: "8px 10px" }}>Alta desde una solicitud express. Al guardar, volvés a la solicitud y el cliente queda vinculado.</p>}
              {error && <p className="error">{error}</p>}
              <div className="sect">
                <div className="lg">Identidad</div>
                <div className="fld"><label>Apellido y nombre <span className="req">*</span></label><input value={form.apellido_nombre} maxLength={80} onChange={(e) => set("apellido_nombre", e.target.value)} /></div>
                <div className="grid2">
                  <div className={`fld ${cuilInvalido ? "err" : ""}`}><label>CUIL <span className="req">*</span></label>
                    <input className="num" inputMode="numeric" value={form.cuil} disabled={!esAlta} maxLength={11}
                      onChange={(e) => set("cuil", e.target.value.replace(/\D/g, "").slice(0, 11))} />
                    <span className="hint">{!esAlta ? "no editable" : (cuilInvalido ? (form.cuil.replace(/\D/g, "").length !== 11 ? "Debe tener 11 dígitos" : "Dígito verificador inválido") : "11 dígitos ✓")}</span></div>
                  <div className={`fld ${dniInvalido ? "err" : ""}`}><label>DNI</label>
                    <input className="num" inputMode="numeric" value={form.dni} maxLength={8} onChange={(e) => set("dni", e.target.value.replace(/\D/g, "").slice(0, 8))} />
                    {dniInvalido && <span className="hint">Debe tener 7 u 8 dígitos</span>}</div>
                  <div className="fld"><label>Sexo</label>
                    <select value={form.sexo} onChange={(e) => set("sexo", e.target.value)}>
                      <option value="">—</option><option value="M">Masculino</option><option value="F">Femenino</option></select></div>
                  <div className="fld"><label>Fecha de nacimiento</label><input type="date" value={form.fecha_nacimiento} onChange={(e) => set("fecha_nacimiento", e.target.value)} /></div>
                </div>
              </div>
              <div className="sect">
                <div className="lg">Contacto</div>
                <div className="fld"><label>Domicilio</label><input value={form.domicilio} maxLength={120} onChange={(e) => set("domicilio", e.target.value)} /></div>
                <div className="grid2">
                  <div className="fld"><label>Barrio</label><input value={form.barrio} maxLength={40} onChange={(e) => set("barrio", e.target.value)} /></div>
                  <div className="fld"><label>Localidad</label><input value={form.localidad} maxLength={40} onChange={(e) => set("localidad", e.target.value)} /></div>
                  <div className="fld"><label>Teléfono</label><input value={form.telefono} maxLength={30} onChange={(e) => set("telefono", e.target.value)} /></div>
                  <div className={`fld ${emailInvalido ? "err" : ""}`}><label>Email</label><input type="email" value={form.email} maxLength={80} onChange={(e) => set("email", e.target.value)} />
                    {emailInvalido && <span className="hint">Email inválido</span>}</div>
                </div>
              </div>
              <div className="sect">
                <div className="lg">Laboral</div>
                <div className="fld"><label>Organismo</label>
                  <select value={form.organismo_id} onChange={(e) => set("organismo_id", e.target.value)}>
                    <option value="">—</option>
                    {organismos.map((o) => <option key={o.id} value={o.id}>{o.nombre}</option>)}
                  </select></div>
                <div className="grid2">
                  <div className="fld"><label>Función / categoría</label><input value={form.categoria_funcion} maxLength={10} onChange={(e) => set("categoria_funcion", e.target.value)} /></div>
                  <div className={`fld ${sueldoInvalido ? "err" : ""}`}><label>Sueldo</label><input className="num" inputMode="decimal" value={form.sueldo} onChange={(e) => set("sueldo", e.target.value.replace(/[^\d.]/g, ""))} />
                    {sueldoInvalido && <span className="hint">Debe ser un número ≥ 0</span>}</div>
                  <div className="fld"><label>Fecha de ingreso</label><input type="date" value={form.fecha_ingreso} onChange={(e) => set("fecha_ingreso", e.target.value)} /></div>
                  <div className="fld"><label>Tipo de cliente</label>
                    <select value={form.tipo_cliente} onChange={(e) => set("tipo_cliente", e.target.value)}>
                      <option value={0}>Agente público</option><option value={1}>Jubilado</option></select></div>
                </div>
              </div>
              <div className="sect">
                <div className="lg">Bancario</div>
                <div className={`fld ${cbuInvalido ? "err" : ""}`}><label>CBU</label><input className="num" inputMode="numeric" value={form.cbu} maxLength={22} onChange={(e) => set("cbu", e.target.value.replace(/\D/g, "").slice(0, 22))} />
                  {cbuInvalido && <span className="hint">El CBU debe tener 22 dígitos ({cbuDigits.length}/22)</span>}</div>
                <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
                  <input type="checkbox" checked={!!form.debito_automatico} onChange={(e) => set("debito_automatico", e.target.checked)} style={{ marginBottom: 0 }} />
                  Débito automático de cuotas</label>
              </div>
            </div>
            <div className="dfoot">
              {!esAlta && <button className="btn-danger" onClick={() => { darBaja(form); setForm(null); }}>Dar de baja</button>}
              <div className="sp" />
              <button className="btn-ghost" onClick={() => setForm(null)}>Cancelar</button>
              <button disabled={guardando || !puedeGuardar} onClick={guardar}>
                {guardando ? "Guardando…" : esAlta ? "Crear cliente" : "Guardar cambios"}
              </button>
            </div>
          </aside>
        </>
      )}
    </>
  );
}
