import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronRight, Copy, Plus, Trash2 } from "lucide-react";
import { borrarCuenta, crearCuenta, editarCuenta, listarCuentas, mensajeDeError } from "../../../api/contabilidad";
import { PermissionGate } from "../../../components/PrivateRoute";
import { useHasPermission } from "../../../context/usePermissions";
import { Alerta, Boton, Card, Field, PageHeader } from "../../../components/ui";
import { Confirmacion } from "../../../components/ui/Confirmacion";
import { Pill } from "../../../components/ui/Pill";

/**
 * Plan de cuentas (igual que en el sistema anterior): a la izquierda el árbol jerárquico, plegable y
 * con buscador; a la derecha los datos de la cuenta elegida. Cada rama tiene su "＋" para agregar una
 * subcuenta con el código ya sugerido, y la cuenta que se está creando aparece en el árbol para ver
 * dónde va a quedar.
 */
const RUBRO_DE_RAIZ = { 1: "ACTIVO", 2: "PASIVO", 3: "PATRIMONIO", 4: "INGRESO", 5: "EGRESO" };
const COLOR_RUBRO = {
  ACTIVO: "bg-blue-500", PASIVO: "bg-amber-500", PATRIMONIO: "bg-purple-500",
  INGRESO: "bg-green-500", EGRESO: "bg-red-500", ORDEN: "bg-gray-400",
};
const ACREEDORAS = ["PASIVO", "PATRIMONIO", "INGRESO"];
const MONEDAS = ["ARS", "USD", "EUR"];

const cmp = (a, b) => a.localeCompare(b, undefined, { numeric: true });
const padreDe = (codigo) => codigo.split(".").slice(0, -1).join(".");
const rubroDeRaiz = (codigo) => RUBRO_DE_RAIZ[codigo.split(".")[0]] || "ACTIVO";

const VACIA = () => ({ id: 0, codigo: "", nombre: "", rubro: "ACTIVO", imputable: true,
                       saldo_normal: "DEUDOR", moneda: "ARS", ajustable: false, requiere_centro: false,
                       descripcion: "", activa: true });

/** Árbol a partir de los códigos: 1 → 1.1 → 1.1.01. Las ramas sin cuenta propia también aparecen. */
function armarArbol(cuentas) {
  const nodos = new Map();
  const asegurar = (codigo) => {
    if (!nodos.has(codigo)) nodos.set(codigo, { codigo, cuenta: null, hijos: [] });
    return nodos.get(codigo);
  };
  cuentas.forEach((c) => { asegurar(c.codigo).cuenta = c; });
  [...nodos.keys()].forEach((codigo) => {
    const segs = codigo.split(".");
    for (let i = 1; i < segs.length; i++) asegurar(segs.slice(0, i).join("."));
  });
  const raices = [];
  nodos.forEach((n) => {
    const padre = n.codigo.includes(".") ? nodos.get(padreDe(n.codigo)) : null;
    (padre ? padre.hijos : raices).push(n);
  });
  const ordenar = (arr) => { arr.sort((a, b) => cmp(a.codigo, b.codigo)); arr.forEach((n) => ordenar(n.hijos)); };
  ordenar(raices);
  return raices;
}

/** Próximo código libre bajo un padre: 1.1 → 1.1.01, 1.1.02… */
function proximoCodigo(padre, hermanos) {
  const max = hermanos.reduce((m, h) => {
    const n = parseInt(h.split(".").pop(), 10);
    return isNaN(n) ? m : Math.max(m, n);
  }, 0);
  const sufijo = String(max + 1).padStart(2, "0");
  return padre ? `${padre}.${sufijo}` : sufijo;
}

export default function PlanCuentasPage() {
  const puedeEditar = useHasPermission("contabilidad", "definiciones:write");
  const [cuentas, setCuentas] = useState([]);
  const [rubros, setRubros] = useState([]);
  const [sel, setSel] = useState("");
  const [borrador, setBorrador] = useState(null);     // copia editable (alta o edición)
  const [esAlta, setEsAlta] = useState(false);
  const [sucio, setSucio] = useState(false);
  const [colapsados, setColapsados] = useState(new Set());
  const [busqueda, setBusqueda] = useState("");
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [cargando, setCargando] = useState(true);
  const [confirmando, setConfirmando] = useState(null);
  const nombreRef = useRef(null);

  const cargar = () =>
    listarCuentas()
      .then((d) => { setCuentas(d.items); setRubros(d.rubros); })
      .catch((e) => setError(mensajeDeError(e)))
      .finally(() => setCargando(false));
  useEffect(() => { cargar(); }, []);   // eslint-disable-line react-hooks/exhaustive-deps

  const cuentaSel = cuentas.find((c) => c.codigo === sel) || null;

  // La cuenta en borrador se muestra en el árbol, para ver dónde va a quedar.
  const vista = useMemo(() => {
    if (esAlta && borrador) {
      return [...cuentas.filter((c) => c.codigo !== borrador.codigo),
              { ...borrador, id: -1, nombre: borrador.nombre || "Nueva cuenta…" }];
    }
    return cuentas;
  }, [cuentas, esAlta, borrador]);
  const arbol = useMemo(() => armarArbol(vista), [vista]);
  const activo = esAlta && borrador ? borrador.codigo : sel;

  useEffect(() => {
    if (esAlta) return;
    setBorrador(cuentaSel ? { ...cuentaSel, saldo_normal: cuentaSel.saldoNormal,
                              requiere_centro: cuentaSel.requiereCentro } : null);
    setSucio(false); setError("");
  }, [sel, cuentas]);   // eslint-disable-line react-hooks/exhaustive-deps

  const q = busqueda.trim().toLowerCase();
  const coincide = (n) => !!n.cuenta && `${n.cuenta.codigo} ${n.cuenta.nombre}`.toLowerCase().includes(q);
  const coincideRama = (n) => coincide(n) || n.hijos.some(coincideRama);

  const cambiar = (patch) => { setBorrador((d) => (d ? { ...d, ...patch } : d)); setSucio(true); };
  const plegar = (codigo) => setColapsados((p) => {
    const s = new Set(p);
    s.has(codigo) ? s.delete(codigo) : s.add(codigo);
    return s;
  });

  /** Si hay cambios sin guardar, se avisa antes de perderlos. */
  const seguir = (accion) => {
    if (!sucio) { accion(); return; }
    setConfirmando({
      titulo: "Cambios sin guardar", mensaje: "Hay cambios sin guardar en la cuenta. ¿Descartarlos?",
      confirmar: "Descartar", onSi: () => { setConfirmando(null); setSucio(false); accion(); },
    });
  };

  const elegir = (nodo) => seguir(() => {
    if (nodo.cuenta && nodo.cuenta.id > 0) { setEsAlta(false); setSel(nodo.codigo); return; }
    // Rama sin cuenta propia: se ofrece crearla (de agrupación), con el código fijo.
    const nueva = { ...VACIA(), codigo: nodo.codigo, imputable: false, rubro: rubroDeRaiz(nodo.codigo) };
    nueva.saldo_normal = ACREEDORAS.includes(nueva.rubro) ? "ACREEDOR" : "DEUDOR";
    setEsAlta(true); setSel(nodo.codigo); setBorrador(nueva); setSucio(false);
    setTimeout(() => nombreRef.current?.focus(), 30);
  });

  const nuevaBajo = (padre) => seguir(() => {
    const hermanos = cuentas.filter((c) => padreDe(c.codigo) === padre).map((c) => c.codigo);
    const cuentaPadre = cuentas.find((c) => c.codigo === padre);
    const rubro = cuentaPadre?.rubro || rubroDeRaiz(padre || "1");
    setColapsados((p) => { const s = new Set(p); s.delete(padre); return s; });
    setEsAlta(true); setSel("");
    setBorrador({ ...VACIA(), codigo: proximoCodigo(padre, hermanos), rubro,
                  saldo_normal: ACREEDORAS.includes(rubro) ? "ACREEDOR" : "DEUDOR" });
    setSucio(true); setError("");
    setTimeout(() => nombreRef.current?.focus(), 30);
  });

  const duplicar = () => cuentaSel && seguir(() => {
    const padre = padreDe(cuentaSel.codigo);
    const hermanos = cuentas.filter((c) => padreDe(c.codigo) === padre).map((c) => c.codigo);
    setEsAlta(true); setSel("");
    setBorrador({ ...cuentaSel, id: 0, saldo_normal: cuentaSel.saldoNormal,
                  requiere_centro: cuentaSel.requiereCentro,
                  codigo: proximoCodigo(padre, hermanos), nombre: `${cuentaSel.nombre} (copia)` });
    setSucio(true);
    setTimeout(() => nombreRef.current?.focus(), 30);
  });

  const guardar = async () => {
    if (!borrador) return;
    setError("");
    if (!borrador.codigo.trim() || !borrador.nombre.trim()) {
      setError("El código y el nombre son obligatorios."); return;
    }
    const datos = {
      codigo: borrador.codigo.trim(), nombre: borrador.nombre.trim(), rubro: borrador.rubro,
      imputable: borrador.imputable, saldo_normal: borrador.saldo_normal, moneda: borrador.moneda,
      ajustable: borrador.ajustable, requiere_centro: borrador.requiere_centro,
      descripcion: borrador.descripcion || "", activa: borrador.activa,
    };
    try {
      const guardada = esAlta ? await crearCuenta(datos) : await editarCuenta(borrador.id, datos);
      await cargar();
      setEsAlta(false); setSucio(false); setSel(guardada.codigo);
      setOk(esAlta ? `Cuenta ${guardada.codigo} creada.` : "Cuenta actualizada.");
    } catch (e) { setError(mensajeDeError(e)); }
  };

  const descartar = () => {
    setEsAlta(false); setSucio(false); setError("");
    setBorrador(cuentaSel ? { ...cuentaSel, saldo_normal: cuentaSel.saldoNormal,
                              requiere_centro: cuentaSel.requiereCentro } : null);
  };

  const borrar = () => cuentaSel && setConfirmando({
    titulo: `Borrar la cuenta ${cuentaSel.codigo}`, confirmar: "Borrar", danger: true,
    mensaje: `${cuentaSel.nombre}\nSólo se borra una cuenta que nunca se usó; si tiene movimientos, dala de baja.`,
    onSi: async () => {
      setConfirmando(null);
      try {
        await borrarCuenta(cuentaSel.id);
        setSel(""); setBorrador(null); setOk("Cuenta borrada."); await cargar();
      } catch (e) { setError(mensajeDeError(e)); }
    },
  });

  /** Ramas del árbol, con su plegado y el filtro de búsqueda. */
  const ramas = (nodos, nivel = 0) => nodos.flatMap((n) => {
    if (q && !coincideRama(n)) return [];
    const abierto = q ? true : !colapsados.has(n.codigo);
    const c = n.cuenta;
    const agrupacion = !c || !c.imputable;
    const fantasma = c && c.id === -1;
    const filas = [(
      <div key={n.codigo}
           onClick={() => elegir(n)}
           className={`flex items-center gap-1.5 pr-2 py-1 rounded-md cursor-pointer text-sm ${
             n.codigo === activo ? "bg-blue-50 text-blue-800" : "hover:bg-gray-50"} ${
             fantasma ? "italic text-gray-500" : ""}`}
           style={{ paddingLeft: 8 + nivel * 16 }}>
        <button type="button" aria-label={n.hijos.length ? `Plegar ${n.codigo}` : undefined}
                onClick={(e) => { if (n.hijos.length) { e.stopPropagation(); plegar(n.codigo); } }}
                className={`w-4 h-4 flex items-center justify-center text-gray-400 ${n.hijos.length ? "" : "invisible"}`}>
          <ChevronRight size={14} className={abierto ? "rotate-90 transition-transform" : "transition-transform"} />
        </button>
        <span className={`w-2 h-2 rounded-full shrink-0 ${COLOR_RUBRO[c?.rubro || rubroDeRaiz(n.codigo)]}`} />
        <span className={`truncate ${agrupacion ? "font-semibold text-gray-800" : "text-gray-700"}`}>
          {c ? c.nombre : <span className="text-gray-400">sin nombre</span>}
        </span>
        {c && !c.activa && <Pill tono="crit">baja</Pill>}
        <span className="flex-1" />
        {puedeEditar && (
          <button type="button" aria-label={`Agregar subcuenta de ${n.codigo}`} title="Agregar subcuenta"
                  onClick={(e) => { e.stopPropagation(); nuevaBajo(n.codigo); }}
                  className="text-gray-300 hover:text-blue-600 px-1">
            <Plus size={14} />
          </button>
        )}
        <span className="text-xs text-gray-400 tabular-nums">{n.codigo}</span>
      </div>
    )];
    if (n.hijos.length && abierto) filas.push(...ramas(n.hijos, nivel + 1));
    return filas;
  });

  const d = borrador;

  return (
    <div className="space-y-4">
      <PageHeader titulo="Plan de cuentas"
                  descripcion={`Árbol de cuentas con sus datos e imputación. ${cuentas.length} cuentas.`}>
        <PermissionGate moduleCode="contabilidad" action="definiciones:write">
          <Boton variante="secundario" onClick={() => nuevaBajo("")}>＋ Cuenta principal</Boton>
        </PermissionGate>
      </PageHeader>

      <Alerta>{error}</Alerta>
      {ok && <Alerta tipo="ok">{ok}</Alerta>}

      <div className="grid lg:grid-cols-[1fr_380px] gap-4 items-start">
        <Card padding={false}>
          <div className="px-3 py-2 border-b border-gray-200">
            <input className="input w-full" placeholder="Buscar por código o nombre"
                   aria-label="Buscar cuenta" value={busqueda} onChange={(e) => setBusqueda(e.target.value)} />
          </div>
          <div className="p-2 max-h-[70vh] overflow-auto">
            {cargando ? <p className="py-8 text-center text-sm text-gray-400">Cargando…</p> : ramas(arbol)}
            {!cargando && arbol.length === 0 && (
              <p className="py-8 text-center text-sm text-gray-400">El plan está vacío.</p>
            )}
          </div>
        </Card>

        <Card>
          {!d ? (
            <p className="text-sm text-gray-500 py-8 text-center">
              Elegí una cuenta del árbol para ver y editar sus datos, o tocá el “＋” de una rama para
              agregarle una subcuenta.
            </p>
          ) : (
            <div className="space-y-3">
              <div className="flex items-start gap-2">
                <div className="mr-auto">
                  <h2 className="font-semibold text-gray-800">{esAlta ? "Nueva cuenta" : "Datos de la cuenta"}</h2>
                  <p className="text-xs text-gray-500">
                    {d.enUso ? `${d.movimientos} movimiento(s) registrados` : "Sin movimientos"}
                  </p>
                </div>
                {!esAlta && puedeEditar && (
                  <>
                    <button type="button" aria-label="Duplicar cuenta" title="Duplicar"
                            onClick={duplicar} className="p-1.5 text-gray-400 hover:text-blue-600 rounded-lg">
                      <Copy size={15} />
                    </button>
                    <button type="button" aria-label="Borrar cuenta" title="Borrar"
                            onClick={borrar} className="p-1.5 text-gray-400 hover:text-red-600 rounded-lg">
                      <Trash2 size={15} />
                    </button>
                  </>
                )}
              </div>

              <div className="grid grid-cols-2 gap-3">
                <Field label="Código">
                  <input className="input w-full tabular-nums" value={d.codigo} disabled={!puedeEditar || d.enUso}
                         onChange={(e) => cambiar({ codigo: e.target.value })} />
                </Field>
                <Field label="Rubro">
                  <select className="input w-full" value={d.rubro} disabled={!puedeEditar || d.enUso}
                          onChange={(e) => cambiar({
                            rubro: e.target.value,
                            saldo_normal: ACREEDORAS.includes(e.target.value) ? "ACREEDOR" : "DEUDOR" })}>
                    {rubros.map((r) => <option key={r} value={r}>{r}</option>)}
                  </select>
                </Field>
              </div>

              <Field label="Nombre">
                <input ref={nombreRef} className="input w-full" value={d.nombre} disabled={!puedeEditar}
                       onChange={(e) => cambiar({ nombre: e.target.value })} />
              </Field>

              <div className="grid grid-cols-2 gap-3">
                <Field label="Saldo normal">
                  <select className="input w-full" value={d.saldo_normal} disabled={!puedeEditar}
                          onChange={(e) => cambiar({ saldo_normal: e.target.value })}>
                    <option value="DEUDOR">Deudor</option><option value="ACREEDOR">Acreedor</option>
                  </select>
                </Field>
                <Field label="Moneda">
                  <select className="input w-full" value={d.moneda} disabled={!puedeEditar}
                          onChange={(e) => cambiar({ moneda: e.target.value })}>
                    {MONEDAS.map((m) => <option key={m} value={m}>{m}</option>)}
                  </select>
                </Field>
              </div>

              <Field label="Descripción">
                <textarea className="input w-full" rows={2} value={d.descripcion || ""} disabled={!puedeEditar}
                          onChange={(e) => cambiar({ descripcion: e.target.value })} />
              </Field>

              <div className="space-y-1.5 text-sm text-gray-600">
                <label className="flex items-center gap-2">
                  <input type="checkbox" checked={d.imputable} disabled={!puedeEditar || d.enUso}
                         onChange={(e) => cambiar({ imputable: e.target.checked })} />
                  Imputable (recibe asientos; si no, es una cuenta de agrupación)
                </label>
                <label className="flex items-center gap-2">
                  <input type="checkbox" checked={d.ajustable} disabled={!puedeEditar}
                         onChange={(e) => cambiar({ ajustable: e.target.checked })} />
                  Se ajusta por inflación
                </label>
                <label className="flex items-center gap-2">
                  <input type="checkbox" checked={d.requiere_centro} disabled={!puedeEditar}
                         onChange={(e) => cambiar({ requiere_centro: e.target.checked })} />
                  Exige centro de costo
                </label>
                <label className="flex items-center gap-2">
                  <input type="checkbox" checked={d.activa} disabled={!puedeEditar}
                         onChange={(e) => cambiar({ activa: e.target.checked })} />
                  Activa
                </label>
              </div>

              {d.enUso && (
                <p className="text-xs text-gray-500">
                  La cuenta tiene movimientos: el código, el rubro y la imputabilidad quedan fijos. Para
                  dejar de usarla, sacale la marca “Activa”.
                </p>
              )}

              {puedeEditar && (
                <div className="flex gap-2 pt-1">
                  <Boton disabled={!sucio} onClick={guardar}>{esAlta ? "Crear cuenta" : "Guardar"}</Boton>
                  <Boton variante="secundario" disabled={!sucio && !esAlta} onClick={descartar}>Descartar</Boton>
                </div>
              )}
            </div>
          )}
        </Card>
      </div>

      {confirmando && (
        <Confirmacion titulo={confirmando.titulo} mensaje={confirmando.mensaje}
                      confirmar={confirmando.confirmar} danger={confirmando.danger !== false}
                      onConfirmar={confirmando.onSi} onCancelar={() => setConfirmando(null)} />
      )}
    </div>
  );
}
