import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { FileText, Landmark, Banknote, RefreshCw, Package, Inbox } from "lucide-react";
import { creditos } from "../../../../api/creditos";
import { PageHeader, Card, Boton, Alerta, Modal, Field } from "../../components/ui";
import { Pill } from "../../components/Pill";
import { fecha } from "../../components/format";

/**
 * Inbox = cuadro de control del workflow: primero las AGRUPACIONES por tipo con su cantidad; al
 * entrar en una, la lista de lo que hay que aprobar o resolver. Cuatro-ojos: el inbox no muestra lo
 * que envió el propio usuario.
 */
const GRUPOS = [
  { tipo: "SOLICITUD", label: "Solicitudes de crédito", icon: FileText, desc: "Solicitudes que esperan evaluación / aprobación." },
  { tipo: "LINEA", label: "Líneas de crédito", icon: Landmark, desc: "Publicación de líneas (Configurar Créditos)." },
  { tipo: "DESEMBOLSO", label: "Desembolsos", icon: Banknote, desc: "Liquidaciones y desembolsos por aprobar." },
  { tipo: "REFINANCIACION", label: "Refinanciaciones", icon: RefreshCw, desc: "Refinanciaciones por aprobar." },
];
const ACCION_LBL = { aprobar: "Aprobar", publicar: "Publicar", resolver: "Resolver" };
const OTROS = "__OTROS__";

export default function InboxAprobacionesPage() {
  const navegar = useNavigate();
  const [items, setItems] = useState([]);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [cargando, setCargando] = useState(true);
  const [grupoSel, setGrupoSel] = useState(null);
  const [rechazando, setRechazando] = useState(null);      // tarea a rechazar
  const [motivo, setMotivo] = useState("");

  async function cargar() {
    setError(""); setCargando(true);
    try { setItems((await creditos.inboxAprobaciones()).items); }
    catch (e) { setError(e.message); }
    finally { setCargando(false); }
  }
  useEffect(() => { cargar(); }, []);

  const grupos = useMemo(() => {
    const conteo = {};
    items.forEach((t) => { conteo[t.tipo] = (conteo[t.tipo] || 0) + 1; });
    const base = GRUPOS.map((g) => ({ ...g, count: conteo[g.tipo] || 0 }));
    const otros = items.filter((t) => !GRUPOS.some((g) => g.tipo === t.tipo));
    if (otros.length) base.push({ tipo: OTROS, label: "Otros", icon: Package, desc: "Otras tareas pendientes.", count: otros.length });
    return base;
  }, [items]);

  const itemsGrupo = useMemo(() => {
    if (!grupoSel) return [];
    if (grupoSel === OTROS) return items.filter((t) => !GRUPOS.some((g) => g.tipo === t.tipo));
    return items.filter((t) => t.tipo === grupoSel);
  }, [items, grupoSel]);
  const grupoActual = grupos.find((g) => g.tipo === grupoSel);

  function abrir(t) {
    if (t.deepLink) sessionStorage.setItem(t.deepLink.clave, t.deepLink.valor);
    navegar(t.ruta);
  }

  async function aprobar(t) {
    setError(""); setOk("");
    try {
      const r = await creditos.inboxAprobarPendiente(t.id);
      setOk(r.ejecutado ? "Aprobado y ejecutado." : `Aprobado. Falta${r.faltan === 1 ? "" : "n"} ${r.faltan} nivel(es).`);
      cargar();
    } catch (e) { setError(e.message); }
  }

  async function rechazar() {
    setError(""); setOk("");
    try {
      await creditos.inboxRechazarPendiente(rechazando.id, motivo);
      setRechazando(null); setMotivo("");
      cargar();
    } catch (e) { setError(e.message); setRechazando(null); }
  }

  return (
    <>
      <PageHeader
        titulo="Inbox de aprobaciones"
        descripcion={grupoSel
          ? grupoActual?.desc
          : "Tu cuadro de control: elegí una agrupación para ver lo pendiente. Cuatro-ojos: no ves lo que vos mismo enviaste."}
      >
        <span className="text-xs uppercase tracking-wide text-gray-500 border rounded-full px-2.5 py-1">
          {items.length} pendiente{items.length === 1 ? "" : "s"}
        </span>
        <Boton variante="secundario" onClick={cargar} disabled={cargando}>
          {cargando ? "…" : "↻ Refrescar"}
        </Boton>
      </PageHeader>

      {error && <div className="mb-4"><Alerta>{error}</Alerta></div>}
      {ok && <div className="mb-4"><Alerta tipo="ok">{ok}</Alerta></div>}

      {!cargando && !items.length && (
        <Card className="text-center text-gray-500 py-10">
          <Inbox size={28} className="mx-auto mb-2 text-gray-300" />
          No tenés tareas pendientes.
        </Card>
      )}

      {!grupoSel && items.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {grupos.map((g) => {
            const Icono = g.icon;
            return (
              <button
                key={g.tipo}
                disabled={!g.count}
                onClick={() => g.count && setGrupoSel(g.tipo)}
                className={`relative text-left bg-surface border rounded-xl p-4 transition-colors ${
                  g.count ? "border-gray-200 hover:border-blue-400" : "border-gray-200 opacity-50 cursor-default"}`}
              >
                <span className={`w-11 h-11 rounded-xl grid place-items-center ${
                  g.count ? "bg-blue-50 text-blue-600" : "bg-gray-50 text-gray-300"}`}>
                  <Icono size={20} />
                </span>
                <span className={`absolute top-4 right-4 text-2xl font-bold tabular-nums ${
                  g.count ? "text-blue-600" : "text-gray-300"}`}>{g.count}</span>
                <p className="font-semibold text-gray-800 mt-2">{g.label}</p>
                <p className="text-xs text-gray-500">{g.desc}</p>
                {g.count > 0 && <p className="text-xs font-semibold text-blue-600 mt-2">Ver {g.count} →</p>}
              </button>
            );
          })}
        </div>
      )}

      {grupoSel && (
        <>
          <div className="flex items-center gap-3 mb-3">
            <Boton variante="secundario" onClick={() => setGrupoSel(null)}>← Panel</Boton>
            <b className="text-gray-800">{grupoActual?.label}</b>
            <span className="ml-auto text-xs uppercase tracking-wide text-gray-500 border rounded-full px-2.5 py-1">
              {itemsGrupo.length}
            </span>
          </div>

          <div className="flex flex-col gap-2">
            {itemsGrupo.map((t) => (
              <div key={`${t.tipo}-${t.id}-${t.estado}`}
                   className="flex items-center gap-4 bg-surface border border-gray-200 rounded-xl px-4 py-3">
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-gray-800">{t.titulo}</p>
                  <p className="text-sm text-gray-500">{t.detalle}</p>
                  <p className="flex flex-wrap items-center gap-2 text-xs text-gray-400 mt-1">
                    <span>Pedido por <b>{t.solicitante}</b></span>
                    {t.fecha && <span>· {fecha(t.fecha)}</span>}
                    <Pill>{t.estado}</Pill>
                  </p>
                </div>
                {t.accion === "aprobar-inline" ? (
                  <div className="flex gap-2 shrink-0">
                    <Boton variante="secundario" className="!text-red-600 !border-red-300"
                           onClick={() => { setRechazando(t); setMotivo(""); }}>Rechazar</Boton>
                    <Boton onClick={() => aprobar(t)}>Aprobar</Boton>
                  </div>
                ) : (
                  <Boton className="shrink-0" onClick={() => abrir(t)}>
                    {ACCION_LBL[t.accion] || t.accion} →
                  </Boton>
                )}
              </div>
            ))}
          </div>
        </>
      )}

      {rechazando && (
        <Modal
          titulo="Rechazar"
          ancho="max-w-md"
          onClose={() => setRechazando(null)}
          footer={
            <>
              <span className="flex-1" />
              <Boton variante="secundario" onClick={() => setRechazando(null)}>Cancelar</Boton>
              <Boton variante="danger" onClick={rechazar}>Rechazar</Boton>
            </>
          }
        >
          <p className="text-sm text-gray-600 mb-3">{rechazando.titulo}</p>
          <Field label="Motivo del rechazo">
            <input className="input w-full" value={motivo} autoFocus onChange={(e) => setMotivo(e.target.value)} />
          </Field>
        </Modal>
      )}
    </>
  );
}
