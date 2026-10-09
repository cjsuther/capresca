import { useEffect, useState } from "react";
import { creditos } from "../../../../../api/creditos";
import { Alerta, Field } from "../../../components/ui";
import { fecha } from "../../../components/format";

/** Rango de monto y cuotas de una línea de la oferta (vienen en `cfg`, las condiciones de la versión vigente). */
export function rangoLinea(l) {
  const c = l?.cfg || l || {};
  const r = { montoMin: Number(c.montoMin), montoMax: Number(c.montoMax), plazoMin: Number(c.plazoMin), plazoMax: Number(c.plazoMax) };
  return Object.values(r).every((x) => Number.isFinite(x)) ? r : null;
}

/** Monto y cuotas dentro del rango de la línea (al elegirla o al cambiarla). */
export function enRangoDe(l, monto, plazo) {
  const r = rangoLinea(l);
  if (!r) return { monto, plazo };
  return { monto: Math.min(r.montoMax, Math.max(r.montoMin, Number(monto) || r.montoMin)),
           plazo: Math.min(r.plazoMax, Math.max(r.plazoMin, Number(plazo) || r.plazoMin)) };
}

/** Sueldo con formato de moneda al mostrarlo; el valor se guarda como número. */
export function CampoSueldo({ valor, onChange, label = "Sueldo neto" }) {
  const [texto, setTexto] = useState(null);           // null = no se está editando: se muestra con formato
  const formateado = valor ? Number(valor).toLocaleString("es-AR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "";
  return (
    <Field label={label}>
      <input inputMode="decimal" className="input w-full tabular-nums" aria-label={label} placeholder="$ 0,00"
             value={texto ?? formateado}
             onFocus={() => setTexto(valor ? String(valor).replace(".", ",") : "")}
             onBlur={() => setTexto(null)}
             onChange={(e) => {
               setTexto(e.target.value);
               const n = parseFloat(e.target.value.replace(/\./g, "").replace(",", "."));
               onChange(isNaN(n) ? "" : Math.max(0, n));
             }} />
    </Field>
  );
}

/** CBU de acreditación: sólo dígitos, avisa cuántos faltan. */
export function CampoCbu({ valor, onChange, requerido }) {
  const d = String(valor || "").replace(/\D/g, "");
  return (
    <Field label={`CBU para acreditar el crédito (22 dígitos)${requerido ? " *" : ""}`}>
      <input inputMode="numeric" maxLength={22} className="input w-full tabular-nums" aria-label="CBU"
             value={d} onChange={(e) => onChange(e.target.value.replace(/\D/g, "").slice(0, 22))} />
      {d && d.length !== 22 && <span className="text-xs text-amber-700">Faltan {22 - d.length} dígito(s).</span>}
    </Field>
  );
}

/**
 * Monto y cuotas de la línea con los mismos controles que el portal: deslizadores dentro del rango de la
 * línea, "¿cuánto puede pedir?" con el sueldo, y la simulación en vivo con la afectación y el cronograma.
 * `onSim` recibe la simulación (o null) para que la pantalla decida si deja seguir.
 */
export function CondicionesCredito({ linea, monto, plazo, sueldo, perfil = {}, onChange, onSim, money }) {
  const [sim, setSim] = useState(null);
  const [preap, setPreap] = useState(null);
  const [calculando, setCalculando] = useState(false);
  const [error, setError] = useState("");
  const rango = rangoLinea(linea);
  const { montoMin = 0, montoMax = 0, plazoMin = 1, plazoMax = 1 } = rango || {};
  // Sin rango conocido o con valores que no son números no se simula: el backend lo rechazaría (422).
  const fuera = !rango || !Number.isFinite(monto) || !Number.isFinite(plazo)
    || monto < montoMin || monto > montoMax || plazo < plazoMin || plazo > plazoMax;

  useEffect(() => {
    if (!linea || fuera) { setSim(null); onSim?.(null); return undefined; }
    const t = setTimeout(async () => {
      setCalculando(true); setError("");
      try {
        const s = await creditos.ppSimPreview(linea.id, {
          monto: Number(monto), plazo: Number(plazo), sueldo: sueldo ? Number(sueldo) : undefined,
          segmento: perfil.segmento || undefined, canal: perfil.canal || undefined,
          fecha_nacimiento: perfil.fecha_nacimiento || undefined,
          antiguedad_meses: perfil.antiguedad_meses === "" || perfil.antiguedad_meses == null ? undefined : Number(perfil.antiguedad_meses),
        });
        setSim(s); onSim?.(s);
      } catch (e) { setSim(null); onSim?.(null); setError(e.message); }
      finally { setCalculando(false); }
    }, 350);
    return () => clearTimeout(t);
  }, [linea?.id, monto, plazo, sueldo, perfil.segmento, perfil.canal, perfil.fecha_nacimiento, perfil.antiguedad_meses]); // eslint-disable-line

  useEffect(() => {
    if (!rango || !Number(sueldo) || !Number.isFinite(plazo) || plazo < plazoMin || plazo > plazoMax) { setPreap(null); return; }
    creditos.ppPreAprobado({ producto_id: linea.id, plazo: Number(plazo), sueldo: Number(sueldo) })
      .then(setPreap).catch(() => setPreap(null));
  }, [linea?.id, plazo, sueldo]); // eslint-disable-line

  if (!linea) return <p className="text-sm text-gray-500">Elegí la línea de crédito.</p>;
  if (!rango) return <Alerta>No se pudieron leer el monto y las cuotas permitidos de esta línea.</Alerta>;

  return (
    <div className="flex flex-col gap-4">
      {preap && (
        <div className="border border-blue-200 bg-blue-50 rounded-lg px-3 py-2 text-sm flex flex-wrap items-center gap-3">
          {preap.monto_maximo > 0 ? (
            <>
              <span className="text-blue-800">
                <b>Puede pedir hasta {money(preap.monto_maximo)}</b> · cuota {money(preap.cuota)} ({preap.afectacion}% del sueldo)
              </span>
              <span className="flex-1" />
              <button type="button" className="text-blue-700 font-medium hover:underline"
                      onClick={() => onChange({ monto: preap.monto_maximo, plazo })}>Usar el máximo</button>
            </>
          ) : (
            <span className="text-blue-800">
              Con este sueldo y plazo la cuota pasa el {preap.afectacion_max}% del sueldo, que es el máximo de la línea: probá más cuotas.
            </span>
          )}
        </div>
      )}

      <div>
        <div className="flex flex-wrap items-baseline gap-2 text-sm">
          <span className="text-gray-600">Monto</span>
          <input type="number" min={montoMin} max={montoMax} step={1000} aria-label="Monto"
                 className="input w-40 tabular-nums" value={monto}
                 onChange={(e) => onChange({ monto: Math.max(0, Math.floor(Number(e.target.value) || 0)), plazo })} />
          <span className="text-xs text-gray-400">{money(montoMin)} – {money(montoMax)}</span>
        </div>
        <input type="range" className="w-full mt-1" aria-label="Monto (deslizador)" min={montoMin} max={montoMax}
               step={Math.max(1, Math.round((montoMax - montoMin) / 200 / 1000) * 1000) || 1000} value={monto}
               onChange={(e) => onChange({ monto: Number(e.target.value), plazo })} />
      </div>

      <div>
        <div className="flex flex-wrap items-baseline gap-2 text-sm">
          <span className="text-gray-600">Cuotas</span>
          <b className="tabular-nums">{plazo}</b>
          <span className="text-xs text-gray-400">({plazoMin}–{plazoMax})</span>
        </div>
        <input type="range" className="w-full mt-1" aria-label="Cuotas" min={plazoMin} max={plazoMax} step={1} value={plazo}
               onChange={(e) => onChange({ monto, plazo: Number(e.target.value) })} />
      </div>

      {fuera && <Alerta tipo="warn">El monto y las cuotas tienen que estar dentro del rango de la línea.</Alerta>}
      {error && <Alerta>{error}</Alerta>}
      <p className="text-xs text-gray-500">{calculando ? "Calculando…" : "La simulación se recalcula sola al cambiar los datos."}</p>

      {sim && !fuera && (
        <div className="border border-gray-200 rounded-xl p-3">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
            <div><p className="text-xs text-gray-500">Primera cuota</p><b className="tabular-nums">{money(sim.primeraCuota)}</b></div>
            <div><p className="text-xs text-gray-500">Total a pagar</p><b className="tabular-nums">{money(sim.totalCuotas)}</b></div>
            <div><p className="text-xs text-gray-500">Intereses</p><b className="tabular-nums">{money(sim.totalInteres)}</b></div>
            <div><p className="text-xs text-gray-500">TNA</p><b>{sim.tna}%</b></div>
          </div>
          {sim.afectacion != null && (
            <p className="text-sm text-gray-600 mt-2">
              La cuota es el <b>{String(sim.afectacion).replace(".", ",")}%</b> del sueldo
              {sim.afectacionMax ? ` (máximo de la línea: ${sim.afectacionMax}%)` : ""}.
            </p>
          )}
          <div className="mt-2">
            {sim.elegible === false
              ? <Alerta>No cumple las condiciones: {sim.motivos.join(" · ")}. Ajustá los datos o elegí otra línea.</Alerta>
              : <Alerta tipo="ok">Elegible con estos datos.</Alerta>}
          </div>
          <details className="mt-2 text-sm">
            <summary className="cursor-pointer text-gray-600">Ver el detalle de las {sim.cantidadCuotas} cuotas</summary>
            <div className="mt-2 max-h-60 overflow-auto border border-gray-200 rounded-lg">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
                    <th className="px-3 py-2 text-left">#</th><th className="px-3 py-2 text-left">Vencimiento</th>
                    <th className="px-3 py-2 text-right">Capital</th><th className="px-3 py-2 text-right">Interés</th>
                    <th className="px-3 py-2 text-right">Cuota</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {sim.cuotas.map((c) => (
                    <tr key={c.numero_cuota}>
                      <td className="px-3 py-1.5 tabular-nums">{c.numero_cuota}</td>
                      <td className="px-3 py-1.5">{fecha(c.fecha_vencimiento)}</td>
                      <td className="px-3 py-1.5 text-right tabular-nums">{money(c.capital)}</td>
                      <td className="px-3 py-1.5 text-right tabular-nums">{money(c.interes)}</td>
                      <td className="px-3 py-1.5 text-right tabular-nums font-semibold">{money(c.total)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </div>
      )}
    </div>
  );
}
