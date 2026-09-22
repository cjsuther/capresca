import { useState } from "react";
import { creditos } from "../../../../api/creditos";
import { PageHeader, Card, Toolbar, Field, Boton, Alerta } from "../../components/ui";
import { Confirmacion } from "../../components/Confirmacion";
import { usePuedeEscribir } from "../../permisos";
import { money, fecha, hoy, num } from "../../components/format";

/**
 * Recálculo del plan pendiente de un crédito (nunca toca cuotas pagadas). Dos modos:
 *  - vencimientos: sólo reprograma la fecha de las cuotas impagas.
 *  - jubilatorio: regenera el plan pendiente como capital puro, cuota = 10% del haber.
 * Siempre con vista previa antes de confirmar.
 */
export default function RecalculoCreditoPage() {
  const puedeEscribir = usePuedeEscribir();
  const [creditoId, setCreditoId] = useState("");
  const [modo, setModo] = useState("vencimientos");
  const [primerVto, setPrimerVto] = useState(hoy());
  const [haber, setHaber] = useState("");
  const [prev, setPrev] = useState(null);
  const [ok, setOk] = useState(null);
  const [error, setError] = useState("");
  const [confirmando, setConfirmando] = useState(false);
  const [ocupado, setOcupado] = useState(false);

  const parametros = () => ({
    modo,
    primer_vto: modo === "vencimientos" ? primerVto : undefined,
    haber: modo === "jubilatorio" ? haber : undefined,
  });

  async function previsualizar(e) {
    e?.preventDefault();
    setError(""); setOk(null); setPrev(null);
    const id = Number(creditoId);
    if (!id) { setError("Ingresá un número de crédito."); return; }
    try { setPrev(await creditos.recalculoPreview(id, parametros())); }
    catch (err) { setError(err.message); }
  }

  async function aplicar() {
    setError(""); setOcupado(true);
    try {
      setOk(await creditos.recalculoAplicar(Number(creditoId), parametros()));
      setPrev(null);
    } catch (err) { setError(err.message); }
    finally { setOcupado(false); setConfirmando(false); }
  }

  const filas = prev ? Math.max(prev.actual.length, prev.propuesto.length) : 0;

  return (
    <>
      <PageHeader
        titulo="Recálculo de cuotas"
        descripcion="Recalcula el plan pendiente de un crédito. Las cuotas ya pagadas no se tocan."
      />

      {error && <div className="mb-4"><Alerta>{error}</Alerta></div>}
      {ok && (
        <div className="mb-4">
          <Alerta tipo="ok">Recálculo aplicado: {num(ok.cuotas_resultantes)} cuotas, total {money(ok.total)}.</Alerta>
        </div>
      )}

      <Card padding={false} className="mb-4">
        <Toolbar>
          <form onSubmit={previsualizar} className="flex flex-wrap items-end gap-3">
            <Field label="N° de crédito">
              <input className="input w-40" value={creditoId} onChange={(e) => setCreditoId(e.target.value)} />
            </Field>
            <Field label="Modo">
              <select className="input" value={modo} onChange={(e) => setModo(e.target.value)}>
                <option value="vencimientos">Reprogramar vencimientos</option>
                <option value="jubilatorio">Jubilatorio (capital, 10% del haber)</option>
              </select>
            </Field>
            {modo === "vencimientos" ? (
              <Field label="1er vto. (cuota 1)">
                <input type="date" className="input" value={primerVto} onChange={(e) => setPrimerVto(e.target.value)} />
              </Field>
            ) : (
              <Field label="Haber jubilatorio">
                <input className="input w-40" value={haber} placeholder="Ej: 250000"
                       onChange={(e) => setHaber(e.target.value)} />
              </Field>
            )}
            <Boton type="submit">Previsualizar</Boton>
          </form>
        </Toolbar>
      </Card>

      {prev && (
        <Card padding={false}>
          <div className="px-4 py-3 border-b border-gray-200">
            <h2 className="font-semibold text-gray-800">Vista previa — {prev.modo}</h2>
            <p className="text-sm text-gray-500 mt-0.5">
              Actual: {num(prev.cantidad_actual)} cuotas ({money(prev.total_actual)}) →
              {" "}Propuesto: {num(prev.cantidad_propuesta)} cuotas ({money(prev.total_propuesto)})
            </p>
          </div>
          <div className="p-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs uppercase tracking-wide text-gray-500">
                  <th colSpan={3} className="px-3 py-2 bg-gray-50 text-left">Actual</th>
                  <th colSpan={3} className="px-3 py-2 bg-blue-50 text-left">Propuesto</th>
                </tr>
                <tr className="border-b border-gray-200 text-xs uppercase tracking-wide text-gray-500">
                  <th className="px-3 py-2 text-left">Cuota</th><th className="px-3 py-2 text-left">Vto</th>
                  <th className="px-3 py-2 text-right">Total</th>
                  <th className="px-3 py-2 text-left">Cuota</th><th className="px-3 py-2 text-left">Vto</th>
                  <th className="px-3 py-2 text-right">Total</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {Array.from({ length: filas }).map((_, i) => {
                  const a = prev.actual[i], p = prev.propuesto[i];
                  const cambia = a && p && a.fecha_vto !== p.fecha_vto;
                  return (
                    <tr key={i} className="hover:bg-gray-50">
                      <td className="px-3 py-2">{a?.numero ?? "—"}</td>
                      <td className="px-3 py-2">{a ? fecha(a.fecha_vto) : "—"}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{a ? money(a.total) : "—"}</td>
                      <td className="px-3 py-2">{p?.numero ?? "—"}</td>
                      <td className={`px-3 py-2 ${cambia ? "text-red-600 font-medium" : ""}`}>
                        {p ? fecha(p.fecha_vto) : "—"}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums">{p ? money(p.total) : "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {puedeEscribir && (
            <div className="px-4 pb-4">
              <Boton variante="danger" onClick={() => setConfirmando(true)}>Confirmar y aplicar recálculo</Boton>
            </div>
          )}
        </Card>
      )}

      {confirmando && (
        <Confirmacion
          titulo="Aplicar el recálculo"
          mensaje={`Se va a reemplazar el plan pendiente del crédito ${creditoId} por las ${num(prev?.cantidad_propuesta)} cuotas propuestas. No se deshace.`}
          confirmar="Aplicar recálculo"
          ocupado={ocupado}
          onConfirmar={aplicar}
          onCancelar={() => setConfirmando(false)}
        />
      )}
    </>
  );
}
