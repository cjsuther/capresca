import { useEffect, useState } from "react";
import { creditos } from "../../../../api/creditos";
import { PageHeader, Card, Field, Alerta } from "../../components/ui";
import { Pill } from "../../components/Pill";
import { num } from "../../components/format";

/**
 * Cómo el motor arma cada cuota: fórmula aplicada, parámetros derivados y depuración paso a paso.
 * La única fuente de verdad es el mismo código que usan la simulación y la originación.
 */
const SIS_LABEL = { FRANCES: "Francés", ALEMAN: "Alemán", AMERICANO: "Americano", BULLET: "Bullet" };

export default function SistemaCalculosPage() {
  const [cat, setCat] = useState(null);
  const [sel, setSel] = useState("FRANCES");
  const [error, setError] = useState("");

  const [params, setParams] = useState({
    monto: 100000, plazo: 6, tna: 52, frecuencia: "MENSUAL", gracia: 0,
    tipoCuota: "VENCIDA", cargoPct: 0,
  });
  const [dbg, setDbg] = useState(null);
  const [expandida, setExpandida] = useState(1);
  const [cargando, setCargando] = useState(false);

  useEffect(() => {
    creditos.sistemaCalculos().then(setCat).catch((e) => setError(e.message));
  }, []);

  // El depurador recalcula solo al mover cualquier parámetro (con debounce).
  useEffect(() => {
    const t = setTimeout(() => {
      setCargando(true);
      creditos.sistemaCalculosDebug({ sistema: sel, ...params })
        .then((d) => { setDbg(d); setError(""); })
        .catch((e) => setError(e.message))
        .finally(() => setCargando(false));
    }, 220);
    return () => clearTimeout(t);
  }, [sel, params]);

  const set = (k, numerico = true) => (e) =>
    setParams((p) => ({ ...p, [k]: numerico ? Number(e.target.value) : e.target.value }));

  const sis = cat?.sistemas.find((s) => s.codigo === sel);
  const cert = cat?.certificacion;

  return (
    <>
      <PageHeader
        titulo="Sistema de cálculos"
        descripcion="Fórmula aplicada, parámetros derivados y depuración cuota por cuota del motor de cálculo."
      >
        {cert && (
          <div className="text-right" title={cert.checksum}>
            <Pill tono="ok">motor certificado</Pill>
            <p className="text-xs text-gray-500 mt-1">
              checksum <b>{cert.checksumCorto}</b> · {cert.reglaRedondeo} · {cert.precisionDecimal} dec.
            </p>
          </div>
        )}
      </PageHeader>

      {error && <div className="mb-4"><Alerta>{error}</Alerta></div>}

      <div className="flex flex-wrap gap-2 mb-4">
        {(cat?.sistemas || []).map((s) => (
          <button
            key={s.codigo}
            onClick={() => setSel(s.codigo)}
            className={`px-3 py-1.5 text-sm rounded-lg border ${
              sel === s.codigo ? "bg-blue-50 border-blue-200 text-blue-700 font-medium"
                               : "border-gray-200 text-gray-600 hover:bg-gray-50"}`}
          >{SIS_LABEL[s.codigo] || s.codigo}</button>
        ))}
      </div>

      {sis && (
        <div className="grid gap-4 lg:grid-cols-2 mb-4">
          <Card>
            <h2 className="font-semibold text-gray-800">{sis.nombre}</h2>
            <p className="text-sm text-gray-500 mt-1">{sis.resumen}</p>
            <pre className="mt-3 p-3 bg-gray-50 border border-gray-200 rounded-lg text-sm overflow-x-auto">{sis.formula}</pre>
            <dl className="mt-3 space-y-1 text-sm">
              {sis.variables.map(([k, d]) => (
                <div key={k} className="flex gap-2">
                  <dt><code className="text-blue-700">{k}</code></dt>
                  <dd className="text-gray-600">{d}</dd>
                </div>
              ))}
            </dl>
          </Card>
          <Card>
            <h2 className="font-semibold text-gray-800">Armado de cada cuota</h2>
            <ol className="mt-2 space-y-1 list-decimal list-inside text-sm text-gray-700">
              {sis.pasos.map((p, i) => <li key={i}><code>{p}</code></li>)}
            </ol>
            {sis.nota && <p className="mt-3 text-sm text-gray-500">{sis.nota}</p>}
          </Card>
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-[300px,1fr]">
        <Card>
          <h2 className="font-semibold text-gray-800 mb-3">Depurador de cuotas</h2>
          <div className="space-y-3">
            <Field label="Monto">
              <input type="number" className="input w-full" value={params.monto} onChange={set("monto")} />
            </Field>
            <Field label="Plazo (cuotas)">
              <input type="number" className="input w-full" value={params.plazo} onChange={set("plazo")} />
            </Field>
            <Field label="TNA %">
              <input type="number" step="0.01" className="input w-full" value={params.tna} onChange={set("tna")} />
            </Field>
            <Field label="Frecuencia">
              <select className="input w-full" value={params.frecuencia} onChange={set("frecuencia", false)}>
                <option value="MENSUAL">Mensual</option>
                <option value="TRIMESTRAL">Trimestral</option>
              </select>
            </Field>
            <Field label="Gracia (cuotas)">
              <input type="number" className="input w-full" value={params.gracia} onChange={set("gracia")} />
            </Field>
            <Field label="Tipo cuota">
              <select className="input w-full" value={params.tipoCuota} onChange={set("tipoCuota", false)}>
                <option value="VENCIDA">Vencida</option>
                <option value="ADELANTADA">Adelantada</option>
              </select>
            </Field>
            <Field label="Cargo otorg. %">
              <input type="number" step="0.01" className="input w-full" value={params.cargoPct} onChange={set("cargoPct")} />
            </Field>
            {cargando && <p className="text-xs text-gray-400">calculando…</p>}
          </div>
        </Card>

        <div className="space-y-4">
          {dbg?.resumen && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {[
                { label: "TNA", valor: `${dbg.resumen.tna}%` },
                { label: "TEA", valor: `${dbg.resumen.tea}%` },
                { label: "CFT", valor: `${dbg.resumen.cft}%` },
                { label: "1ª cuota", valor: `$${num(dbg.resumen.primeraCuota)}` },
              ].map((k) => (
                <div key={k.label} className="bg-surface border border-gray-200 rounded-xl px-4 py-3">
                  <p className="text-xs text-gray-500">{k.label}</p>
                  <p className="text-lg font-semibold text-gray-800">{k.valor}</p>
                </div>
              ))}
            </div>
          )}

          {dbg?.derivados && (
            <Card>
              <h2 className="font-semibold text-gray-800 mb-2">Parámetros derivados</h2>
              <dl className="grid sm:grid-cols-2 gap-x-6 gap-y-1 text-sm">
                {dbg.derivados.map((d) => (
                  <div key={d.nombre} className="flex justify-between gap-3 border-b border-gray-100 py-1">
                    <dt className="text-gray-500">{d.nombre}</dt>
                    <dd><code>{d.valor}</code></dd>
                  </div>
                ))}
              </dl>
            </Card>
          )}

          {dbg?.pasos && (
            <Card padding={false}>
              <p className="px-4 py-3 text-sm text-gray-500 border-b border-gray-200">
                Paso a paso — clickeá una cuota para ver su detalle
              </p>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-gray-50 border-b border-gray-200 text-xs uppercase tracking-wide text-gray-500">
                      <th className="px-3 py-2 text-left">#</th>
                      <th className="px-3 py-2 text-right">Saldo inicial</th>
                      <th className="px-3 py-2 text-right">Interés</th>
                      <th className="px-3 py-2 text-right">Capital</th>
                      <th className="px-3 py-2 text-right">Cuota</th>
                      <th className="px-3 py-2 text-right">Saldo final</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {dbg.pasos.map((p) => [
                      <tr key={p.cuota}
                          onClick={() => setExpandida(expandida === p.cuota ? null : p.cuota)}
                          className={`cursor-pointer hover:bg-gray-50 ${expandida === p.cuota ? "bg-blue-50" : ""} ${
                            p.enGracia ? "text-amber-700" : ""}`}>
                        <td className="px-3 py-2">{p.cuota}{p.enGracia ? " (gracia)" : ""}</td>
                        <td className="px-3 py-2 text-right tabular-nums">{p.saldoInicial}</td>
                        <td className="px-3 py-2 text-right tabular-nums">{p.interes}</td>
                        <td className="px-3 py-2 text-right tabular-nums">{p.capital}</td>
                        <td className="px-3 py-2 text-right tabular-nums font-semibold">{p.cuota_total}</td>
                        <td className="px-3 py-2 text-right tabular-nums">{p.saldoFinal}</td>
                      </tr>,
                      expandida === p.cuota && (
                        <tr key={`${p.cuota}-detalle`} className="bg-gray-50">
                          <td colSpan={6} className="px-4 py-3">
                            <div className="font-mono text-xs text-gray-600 space-y-1">
                              {p.detalle.map((l, i) => <div key={i}>{l}</div>)}
                            </div>
                          </td>
                        </tr>
                      ),
                    ])}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </div>
      </div>

      {cat?.reglasComunes?.length > 0 && (
        <Card className="mt-4">
          <h2 className="font-semibold text-gray-800 mb-2">Reglas comunes a todos los sistemas</h2>
          <dl className="space-y-2 text-sm">
            {cat.reglasComunes.map((r) => (
              <div key={r.titulo}>
                <dt className="font-medium text-gray-700">{r.titulo}</dt>
                <dd className="text-gray-500">{r.detalle}</dd>
              </div>
            ))}
          </dl>
        </Card>
      )}
    </>
  );
}
