import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { creditos } from "../../../../api/creditos";
import { PageHeader, Card, Field, Boton, Alerta } from "../../components/ui";
import { usePuedeEscribir } from "../../permisos";

// Parámetros EXCLUSIVOS de créditos (H-197): canales de venta y decimales del cálculo. Separados de
// los "Parámetros generales" (transversales) y de los contables.
const DESC = {
  CANALES: "Catálogo de canales de venta habilitados (coma-separado).",
  CANAL_PORTAL: "Código de canal habilitado en el portal del ciudadano (solo web).",
  CANAL_BACKOFFICE: "Canal asumido al originar desde el backoffice sin canal explícito.",
  DECIMALES_CALCULO: "Decimales para el REDONDEO del cálculo de las cuotas (0–6).",
  DECIMALES_MOSTRAR: "Decimales con que se MUESTRAN los importes de créditos en pantalla (0–6).",
};

const acotar = (v) => Math.max(0, Math.min(6, Math.floor(Number(v) || 0)));

export default function ParametrosCreditosPage() {
  const puedeEscribir = usePuedeEscribir();
  const [canales, setCanales] = useState([]);
  const [portal, setPortal] = useState("WEB");
  const [backoffice, setBackoffice] = useState("SUCURSAL");
  const [decimales, setDecimales] = useState(2);
  const [decimalesMostrar, setDecimalesMostrar] = useState(2);
  const [nuevoCanal, setNuevoCanal] = useState("");
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");

  async function cargar() {
    setError(""); setCargando(true);
    try {
      const ps = await creditos.adminParametros("creditos");
      const m = {};
      ps.forEach((p) => { m[p.clave] = p.valor; });
      setCanales((m.CANALES || "SUCURSAL,WEB,APP,CONVENIO").split(",").map((s) => s.trim().toUpperCase()).filter(Boolean));
      setPortal((m.CANAL_PORTAL || "WEB").toUpperCase());
      setBackoffice((m.CANAL_BACKOFFICE || "SUCURSAL").toUpperCase());
      setDecimales(acotar(m.DECIMALES_CALCULO ?? 2));
      setDecimalesMostrar(acotar(m.DECIMALES_MOSTRAR ?? 2));
    } catch (e) { setError(e.message); }
    finally { setCargando(false); }
  }
  useEffect(() => { cargar(); }, []);

  const agregarCanal = () => {
    const c = nuevoCanal.trim().toUpperCase();
    if (c && !canales.includes(c)) setCanales([...canales, c]);
    setNuevoCanal("");
  };
  const quitarCanal = (c) => {
    const quedan = canales.filter((x) => x !== c);
    setCanales(quedan);
    if (portal === c) setPortal(quedan[0] || "");
    if (backoffice === c) setBackoffice(quedan[0] || "");
  };

  async function guardar() {
    setError(""); setOk(""); setGuardando(true);
    const up = (clave, valor) =>
      creditos.upsertParametro({ clave, valor, descripcion: DESC[clave] || "", ambito: "creditos" });
    try {
      await up("CANALES", canales.join(","));
      await up("CANAL_PORTAL", portal);
      await up("CANAL_BACKOFFICE", backoffice);
      await up("DECIMALES_CALCULO", String(acotar(decimales)));
      await up("DECIMALES_MOSTRAR", String(acotar(decimalesMostrar)));
      setOk("Parámetros de créditos guardados.");
      cargar();
    } catch (e) { setError(e.message); }
    finally { setGuardando(false); }
  }

  return (
    <>
      <PageHeader
        titulo="Parámetros de créditos"
        descripcion="Configuración exclusiva de créditos: canales de venta y decimales del cálculo."
      />

      {error && <div className="mb-4"><Alerta>{error}</Alerta></div>}
      {ok && <div className="mb-4"><Alerta tipo="ok">{ok}</Alerta></div>}

      {cargando ? <Card>Cargando…</Card> : (
        <>
          <Card className="mb-4">
            <h2 className="font-semibold text-gray-800">Canales de venta</h2>
            <p className="text-sm text-gray-500 mt-0.5 mb-3">
              Catálogo de canales por los que se ofrece un crédito. La disponibilidad por canal se
              define en cada línea (Configurar Créditos → Disponibilidad).
            </p>

            <div className="flex flex-wrap gap-2 mb-3">
              {canales.map((c) => (
                <span key={c} className="inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full bg-blue-50 text-blue-700 border border-blue-200">
                  {c}
                  {puedeEscribir && (
                    <button type="button" aria-label={`Quitar ${c}`} onClick={() => quitarCanal(c)} className="hover:text-blue-900">
                      <X size={12} />
                    </button>
                  )}
                </span>
              ))}
              {!canales.length && <span className="text-sm text-gray-400">Sin canales.</span>}
            </div>

            {puedeEscribir && (
              <div className="flex items-end gap-2 mb-4">
                <input
                  className="input w-64"
                  value={nuevoCanal}
                  maxLength={20}
                  placeholder="Nuevo canal (ej. TELEFONO)"
                  aria-label="Nuevo canal"
                  onChange={(e) => setNuevoCanal(e.target.value.toUpperCase().replace(/[^A-Z0-9_]/g, ""))}
                  onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); agregarCanal(); } }}
                />
                <Boton variante="secundario" onClick={agregarCanal} disabled={!nuevoCanal.trim()}>＋ Agregar</Boton>
              </div>
            )}

            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Canal del portal (público)">
                <select className="input w-full" value={portal} disabled={!puedeEscribir}
                        onChange={(e) => setPortal(e.target.value)}>
                  {canales.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
                <span className="text-xs text-gray-400">Sólo se ofrecen en el portal las líneas con este canal habilitado.</span>
              </Field>
              <Field label="Canal del backoffice (por defecto)">
                <select className="input w-full" value={backoffice} disabled={!puedeEscribir}
                        onChange={(e) => setBackoffice(e.target.value)}>
                  {canales.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
                <span className="text-xs text-gray-400">Canal asumido al originar desde el backoffice sin elegir uno.</span>
              </Field>
            </div>
          </Card>

          <Card className="mb-4">
            <h2 className="font-semibold text-gray-800 mb-3">Cálculo de préstamos</h2>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Decimales para el cálculo (redondeo)">
                <input type="number" min={0} max={6} step={1} className="input w-full" value={decimales}
                       disabled={!puedeEscribir} onChange={(e) => setDecimales(acotar(e.target.value))} />
                <span className="text-xs text-gray-400">
                  Precisión interna (0–6) con que el motor redondea cada cuota. Los contratos ya
                  originados conservan su cronograma (snapshot); aplica a cálculos nuevos.
                </span>
              </Field>
              <Field label="Decimales para mostrar">
                <input type="number" min={0} max={6} step={1} className="input w-full" value={decimalesMostrar}
                       disabled={!puedeEscribir} onChange={(e) => setDecimalesMostrar(acotar(e.target.value))} />
                <span className="text-xs text-gray-400">No cambia el cálculo, sólo la presentación en pantalla.</span>
              </Field>
            </div>
          </Card>

          {puedeEscribir && (
            <div className="flex justify-end">
              <Boton onClick={guardar} disabled={guardando}>
                {guardando ? "Guardando…" : "Guardar parámetros"}
              </Boton>
            </div>
          )}
        </>
      )}
    </>
  );
}
