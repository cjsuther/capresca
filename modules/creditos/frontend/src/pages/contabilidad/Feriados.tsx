import { useEffect, useMemo, useState } from "react";
import { api } from "../../api";
import { confirmar } from "../../ui/dialog";

type Feriado = { id: number; pais: string; fecha: string; nombre: string; tipo: string; origen: string; activo: boolean };
type Pais = { codigo: string; nombre: string };
type SortKey = "fecha" | "nombre" | "tipo" | "origen" | "activo";

const hoyAnio = new Date().getFullYear();
const MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];
const DIAS = ["Lu", "Ma", "Mi", "Ju", "Vi", "Sá", "Do"];

// Color y etiqueta por tipo de feriado (usado en tabla, calendario y leyenda).
const TIPOS: { codigo: string; label: string; color: string }[] = [
  { codigo: "INAMOVIBLE", label: "Inamovible", color: "var(--dv-red)" },      // rojo vivo
  { codigo: "TRASLADABLE", label: "Trasladable", color: "var(--dv-amber)" },  // ámbar dorado
  { codigo: "PUENTE", label: "Puente", color: "var(--dv-purple)" },           // violeta
  { codigo: "NO_LABORABLE", label: "No laborable", color: "var(--dv-teal)" }, // teal
];
const tipoColor = (t: string) => TIPOS.find((x) => x.codigo === t)?.color ?? "var(--dv-slate)";

export default function Feriados() {
  const [paises, setPaises] = useState<Pais[]>([]);
  const [pais, setPais] = useState("AR");
  const [anio, setAnio] = useState(hoyAnio);
  const [items, setItems] = useState<Feriado[]>([]);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [vista, setVista] = useState<"tabla" | "calendario">("tabla");
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: "fecha", dir: 1 });
  const [nuevo, setNuevo] = useState({ fecha: "", nombre: "", tipo: "INAMOVIBLE" });

  useEffect(() => { api.feriadosPaises().then((d) => setPaises(d.items)).catch(() => {}); }, []);

  const cargar = () => api.feriados(pais, anio).then((d) => setItems(d.items)).catch((e) => setErr(String(e)));
  useEffect(() => { cargar(); }, [pais, anio]);

  const importar = async () => {
    setBusy(true); setErr(""); setMsg("");
    try {
      const r = await api.feriadosImportar(pais, anio);
      setMsg(`Importados ${r.importados} feriados de ${r.totalFuente} · fuente: ${r.fuente}`);
      cargar();
    } catch (e) { setErr(String(e)); } finally { setBusy(false); }
  };
  const agregar = async () => {
    if (!nuevo.fecha || !nuevo.nombre.trim()) { setErr("Completá fecha y nombre"); return; }
    setErr(""); setMsg("");
    try {
      await api.feriadoCrear({ pais, fecha: nuevo.fecha, nombre: nuevo.nombre, tipo: nuevo.tipo });
      setNuevo({ fecha: "", nombre: "", tipo: "INAMOVIBLE" });
      cargar();
    } catch (e) { setErr(String(e)); }
  };
  const toggle = async (f: Feriado) => {
    try { await api.feriadoEditar(f.id, { ...f, activo: !f.activo }); cargar(); } catch (e) { setErr(String(e)); }
  };
  const borrar = async (f: Feriado) => {
    if (!(await confirmar({ titulo: "Borrar feriado", danger: true, mensaje: `¿Borrar el feriado "${f.nombre}" (${f.fecha})?` }))) return;
    try { await api.feriadoBorrar(f.id); cargar(); } catch (e) { setErr(String(e)); }
  };

  const sortBy = (key: SortKey) => setSort((s) => ({ key, dir: s.key === key ? (s.dir === 1 ? -1 : 1) : 1 }));
  const sortArrow = (key: SortKey) => sort.key === key ? (sort.dir === 1 ? " ▲" : " ▼") : "";

  const ordenados = useMemo(() => {
    const arr = [...items];
    arr.sort((a, b) => {
      let va: string | number = a[sort.key] as any, vb: string | number = b[sort.key] as any;
      if (sort.key === "activo") { va = a.activo ? 1 : 0; vb = b.activo ? 1 : 0; }
      return va < vb ? -sort.dir : va > vb ? sort.dir : 0;
    });
    return arr;
  }, [items, sort]);

  const porFecha = useMemo(() => {
    const m: Record<string, Feriado> = {};
    items.forEach((f) => { m[f.fecha] = f; });
    return m;
  }, [items]);

  const anios = Array.from({ length: 7 }, (_, i) => hoyAnio - 1 + i);

  return (
    <div className="fer">
      <div className="fer-head">
        <div>
          <h1>Feriados — calendario por país</h1>
          <p className="fer-sub">Días no laborables que el motor de créditos usa para no fechar vencimientos en día inhábil.</p>
        </div>
        <button className="btn primary" disabled={busy} onClick={importar}>
          {busy ? "Importando…" : "⭳ Importar de fuente oficial"}
        </button>
      </div>

      <div className="fer-toolbar">
        <label>País
          <select value={pais} onChange={(e) => setPais(e.target.value)}>
            {paises.map((p) => <option key={p.codigo} value={p.codigo}>{p.nombre} ({p.codigo})</option>)}
          </select>
        </label>
        <label>Año
          <select value={anio} onChange={(e) => setAnio(+e.target.value)}>
            {anios.map((a) => <option key={a} value={a}>{a}</option>)}
          </select>
        </label>
        <span className="fer-count">{items.length} feriados</span>
      </div>

      {msg && <div className="fer-ok">{msg}</div>}
      {err && <div className="fer-err">{err}</div>}

      <div className="fer-add">
        <input type="date" value={nuevo.fecha} onChange={(e) => setNuevo({ ...nuevo, fecha: e.target.value })} />
        <input placeholder="Nombre del feriado" value={nuevo.nombre} onChange={(e) => setNuevo({ ...nuevo, nombre: e.target.value })} />
        <select value={nuevo.tipo} onChange={(e) => setNuevo({ ...nuevo, tipo: e.target.value })}>
          {TIPOS.map((t) => <option key={t.codigo} value={t.codigo}>{t.label}</option>)}
        </select>
        <button className="btn" onClick={agregar}>+ Agregar manual</button>
      </div>

      <div className="fer-bar">
        <div className="fer-vistas">
          <button className={vista === "tabla" ? "on" : ""} onClick={() => setVista("tabla")}>▤ Tabla</button>
          <button className={vista === "calendario" ? "on" : ""} onClick={() => setVista("calendario")}>▦ Calendario</button>
        </div>
        <div className="fer-legend">
          {TIPOS.map((t) => (
            <span key={t.codigo} className="fer-leg"><i style={{ background: t.color }} />{t.label}</span>
          ))}
        </div>
      </div>

      {vista === "tabla" ? (
        <table className="fer-table">
          <thead>
            <tr>
              <th className="srt" onClick={() => sortBy("fecha")}>Fecha{sortArrow("fecha")}</th>
              <th>Día</th>
              <th className="srt" onClick={() => sortBy("nombre")}>Nombre{sortArrow("nombre")}</th>
              <th className="srt" onClick={() => sortBy("tipo")}>Tipo{sortArrow("tipo")}</th>
              <th className="srt" onClick={() => sortBy("origen")}>Origen{sortArrow("origen")}</th>
              <th className="srt" onClick={() => sortBy("activo")}>Activo{sortArrow("activo")}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {ordenados.map((f) => {
              const d = new Date(f.fecha + "T00:00:00");
              const dia = d.toLocaleDateString("es-AR", { weekday: "short" });
              return (
                <tr key={f.id} className={f.activo ? "" : "off"}>
                  <td>{f.fecha}</td>
                  <td className="fer-dia">{dia}</td>
                  <td>{f.nombre}</td>
                  <td><span className="fer-tag" style={{ background: tipoColor(f.tipo) }}>{f.tipo}</span></td>
                  <td><span className={"fer-orig " + (f.origen === "OFICIAL" ? "ofi" : "")}>{f.origen}</span></td>
                  <td><button className="fer-toggle" onClick={() => toggle(f)}>{f.activo ? "● sí" : "○ no"}</button></td>
                  <td><button className="fer-del" onClick={() => borrar(f)} title="Borrar">✕</button></td>
                </tr>
              );
            })}
            {items.length === 0 && <tr><td colSpan={7} className="fer-empty">No hay feriados para {pais} {anio}. Importá de la fuente oficial o agregá manualmente.</td></tr>}
          </tbody>
        </table>
      ) : (
        <div className="fer-cal">
          {MESES.map((mes, mi) => (
            <MesCal key={mi} anio={anio} mes={mi} nombre={mes} porFecha={porFecha} />
          ))}
        </div>
      )}
    </div>
  );
}

function MesCal({ anio, mes, nombre, porFecha }: { anio: number; mes: number; nombre: string; porFecha: Record<string, Feriado> }) {
  const offset = (new Date(anio, mes, 1).getDay() + 6) % 7; // lunes = 0
  const dias = new Date(anio, mes + 1, 0).getDate();
  const celdas: (number | null)[] = [...Array(offset).fill(null), ...Array.from({ length: dias }, (_, i) => i + 1)];
  const iso = (d: number) => `${anio}-${String(mes + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
  const total = celdas.filter((d) => d && porFecha[iso(d)]).length;
  const hoy = new Date();
  const esMesActual = anio === hoy.getFullYear() && mes === hoy.getMonth();
  const diaHoy = esMesActual ? hoy.getDate() : -1;

  return (
    <div className={"fer-mes" + (total ? " con" : "") + (esMesActual ? " act" : "")}>
      <div className="fer-mes-h">
        {nombre}
        {esMesActual && <span className="fer-mes-hoy">● actual</span>}
        {total > 0 && <span className="fer-mes-n">{total}</span>}
      </div>
      <div className="fer-mes-grid">
        {DIAS.map((d, i) => <span key={"h" + i} className="fer-dow">{d}</span>)}
        {celdas.map((d, i) => {
          if (!d) return <span key={i} className="fer-c empty" />;
          const f = porFecha[iso(d)];
          const dow = new Date(anio, mes, d).getDay();
          const finde = dow === 0 || dow === 6;
          return (
            <span key={i}
              className={"fer-c" + (f ? " hol t-" + f.tipo : "") + (f && !f.activo ? " off" : "") + (finde && !f ? " finde" : "") + (d === diaHoy ? " hoy" : "")}
              title={f ? `${f.nombre} · ${f.tipo}` : (d === diaHoy ? "Hoy" : "")}>
              {d}
            </span>
          );
        })}
      </div>
    </div>
  );
}
