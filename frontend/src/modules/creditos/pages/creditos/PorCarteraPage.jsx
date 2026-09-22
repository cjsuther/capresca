import { useEffect, useState } from "react";
import { creditos } from "../../../../api/creditos";
import { PageHeader, Card, Boton, Alerta } from "../../components/ui";
import { money, num } from "../../components/format";

export default function PorCarteraPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => { creditos.situacionPorCartera().then(setData).catch((e) => setError(e.message)); }, []);

  const filas = data?.por_cartera || [];

  return (
    <>
      <PageHeader
        titulo="Créditos por cartera"
        descripcion="Cantidades y situación de créditos agrupados por cartera. El saldo corresponde a los créditos activos."
      >
        <Boton variante="secundario" onClick={() => creditos.verPorCarteraPdf()}>Descargar PDF</Boton>
      </PageHeader>

      {error && <div className="mb-4"><Alerta>{error}</Alerta></div>}

      {data?.anomalias_saldo_negativo > 0 && (
        <div className="mb-4">
          <Alerta tipo="warn">
            {data.anomalias_saldo_negativo} crédito(s) con saldo negativo (dato corrupto del backup) quedan
            fuera del saldo. Ver hallazgo H-023.
          </Alerta>
        </div>
      )}

      <Card padding={false} className="p-4">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
                <th className="px-3 py-2 text-left">Cartera</th>
                <th className="px-3 py-2 text-right">Activos</th>
                <th className="px-3 py-2 text-right">Cancelados</th>
                <th className="px-3 py-2 text-right">Capital otorgado</th>
                <th className="px-3 py-2 text-right">Saldo (activos)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {filas.map((c) => (
                <tr key={c.cartera} className="hover:bg-gray-50">
                  <td className="px-3 py-2 text-gray-700">{c.nombre} <span className="text-gray-400">({c.cartera})</span></td>
                  <td className="px-3 py-2 text-right tabular-nums">{num(c.activos)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{num(c.cancelados)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{money(c.capital)}</td>
                  <td className="px-3 py-2 text-right tabular-nums font-semibold">{money(c.saldo)}</td>
                </tr>
              ))}
              {data && !filas.length && (
                <tr><td colSpan={5} className="px-3 py-8 text-center text-gray-400">Sin créditos</td></tr>
              )}
            </tbody>
            {filas.length > 0 && (
              <tfoot>
                <tr className="border-t-2 border-gray-300 font-semibold text-gray-800">
                  <td className="px-3 py-2">Total</td>
                  <td className="px-3 py-2 text-right tabular-nums">{num(data.total.activos)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{num(data.total.cancelados)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{money(data.total.capital)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{money(data.total.saldo)}</td>
                </tr>
              </tfoot>
            )}
          </table>
        </div>
      </Card>
    </>
  );
}
