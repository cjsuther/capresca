import { Fragment, useEffect, useMemo, useState } from "react";
import { creditos } from "../../../../api/creditos";
import { PageHeader, Card, Boton, Alerta, Kpis } from "../../components/ui";
import { Pill } from "../../components/Pill";
import { ContratoServicing } from "./ContratoServicing";
import { useSoloLectura } from "../../permisos";
import { money, fecha, num } from "../../components/format";

const TONO_ESTADO = {
  ACTIVO: "ok", A_LIQUIDAR: "warn", EN_MORA: "warn", REFINANCIADO: "brand",
  ANULADO: "crit", CASTIGADO: "crit", CERRADO: "neutral", CANCELADO: "neutral",
};

/**
 * Situación del cliente en la línea nueva: sus contratos agrupados por cliente, con el servicing
 * de cada préstamo desplegable en la misma pantalla.
 */
export default function SituacionClienteLineaPage() {
  const soloLectura = useSoloLectura();
  const [q, setQ] = useState("");
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [cargando, setCargando] = useState(false);
  const [detalle, setDetalle] = useState({});

  async function cargar(query = q) {
    setError(""); setCargando(true);
    try { setData(await creditos.ctoSituacion(query)); }
    catch (e) { setError(e.message); }
    finally { setCargando(false); }
  }

  useEffect(() => {
    // Prefill cuando se llega desde otra pantalla (deep link del inbox, por ejemplo).
    const pre = sessionStorage.getItem("situacion_cliente_q");
    if (pre) { sessionStorage.removeItem("situacion_cliente_q"); setQ(pre); cargar(pre); }
    else cargar("");
  }, []); // eslint-disable-line

  async function alternar(id) {
    if (detalle[id]) {
      setDetalle((d) => { const n = { ...d }; delete n[id]; return n; });
      return;
    }
    try { const c = await creditos.ctoObtener(id); setDetalle((d) => ({ ...d, [id]: c })); }
    catch (e) { setError(e.message); }
  }

  const alCambiar = (c) => setDetalle((d) => ({ ...d, [c.id]: c }));
  async function refrescar(id) {
    await cargar();
    if (id) { try { alCambiar(await creditos.ctoObtener(id)); } catch { /* pudo cambiar de estado */ } }
  }

  const r = data?.resumen;

  // Vista centrada en el cliente: un cliente puede tener varios préstamos.
  const grupos = useMemo(() => {
    const m = new Map();
    (data?.items || []).forEach((c) => {
      const k = c.cliente || "—";
      if (!m.has(k)) m.set(k, []);
      m.get(k).push(c);
    });
    return [...m.entries()].sort((a, b) => a[0].localeCompare(b[0])).map(([cliente, ctos]) => ({
      cliente,
      ctos: [...ctos].sort((x, y) => String(x.numero).localeCompare(String(y.numero))),
      saldo: ctos.reduce((s, c) => s + (c.saldo || 0), 0),
      activos: ctos.filter((c) => c.estado === "ACTIVO").length,
      mora: ctos.filter((c) => c.enMora).length,
    }));
  }, [data]);

  return (
    <>
      <PageHeader
        titulo="Situación del cliente (línea nueva)"
        descripcion="Contratos del cliente con su plan, actividades y asientos. Cada préstamo se opera desde su propio panel."
      >
        <input
          className="input w-64"
          value={q}
          placeholder="Buscar por nombre de cliente…"
          aria-label="Buscar por nombre de cliente"
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && cargar()}
        />
        <Boton onClick={() => cargar()} disabled={cargando}>{cargando ? "…" : "Buscar"}</Boton>
        {data?.items?.length > 0 && (
          <Boton variante="ok" onClick={() => creditos.ctoCarteraExcel().catch((e) => setError(e.message))}>
            Excel
          </Boton>
        )}
      </PageHeader>

      {error && <div className="mb-4"><Alerta>{error}</Alerta></div>}

      {r && (
        <div className="mb-4">
          <Kpis items={[
            { label: "Contratos", valor: num(r.contratos) },
            { label: "Activos", valor: num(r.activos), tono: "ok" },
            { label: "En mora", valor: num(r.enMora), tono: r.enMora ? "crit" : undefined },
            { label: "Capital colocado", valor: money(r.capitalColocado) },
            { label: "Saldo vigente", valor: money(r.saldoVigente) },
          ]} />
        </div>
      )}

      {!grupos.length && (
        <Card className="text-center text-gray-500 py-8">
          Buscá un cliente para ver su situación y sus préstamos.
        </Card>
      )}

      {grupos.map((g) => (
        <Card key={g.cliente} padding={false} className="mb-4">
          <div className="flex flex-wrap items-center gap-2 px-4 py-3 border-b border-gray-200">
            <b className="text-gray-800">{g.cliente}</b>
            <span className="text-sm text-gray-500">
              · {g.ctos.length} préstamo{g.ctos.length !== 1 ? "s" : ""}
            </span>
            <span className="flex-1" />
            {g.mora > 0 && <Pill tono="crit">{g.mora} en mora</Pill>}
            <Pill tono="ok">{g.activos} activo{g.activos !== 1 ? "s" : ""}</Pill>
            <span className="text-sm text-gray-500">Saldo total <b className="text-gray-800 tabular-nums">{money(g.saldo)}</b></span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-200 text-xs uppercase tracking-wide text-gray-500">
                  <th className="px-3 py-2 w-8" />
                  <th className="px-3 py-2 text-left">Contrato</th>
                  <th className="px-3 py-2 text-left">Sistema</th>
                  <th className="px-3 py-2 text-right">Monto</th>
                  <th className="px-3 py-2 text-right">Saldo</th>
                  <th className="px-3 py-2 text-right">Cuotas</th>
                  <th className="px-3 py-2 text-left">Próxima cuota</th>
                  <th className="px-3 py-2 text-right">Mora</th>
                  <th className="px-3 py-2 text-left">Estado</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {g.ctos.map((c) => (
                  <Fragment key={c.id}>
                    <tr onClick={() => alternar(c.id)}
                        className={`cursor-pointer hover:bg-gray-50 ${detalle[c.id] ? "bg-blue-50" : ""}`}>
                      <td className="px-3 py-2 text-gray-400">{detalle[c.id] ? "▾" : "▸"}</td>
                      <td className="px-3 py-2 font-medium">{c.numero}</td>
                      <td className="px-3 py-2">{c.sistema}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{money(c.monto)}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{money(c.saldo)}</td>
                      <td className="px-3 py-2 text-right tabular-nums">
                        {c.cuotasPagadas}/{c.cuotasPagadas + c.cuotasPendientes}
                      </td>
                      <td className="px-3 py-2">
                        {c.proximaCuota
                          ? `#${c.proximaCuota.numero} · ${fecha(c.proximaCuota.vencimiento)} · ${money(c.proximaCuota.total)}`
                          : "—"}
                      </td>
                      <td className={`px-3 py-2 text-right tabular-nums ${c.enMora ? "text-red-600 font-medium" : ""}`}>
                        {c.moraAlDia > 0 ? money(c.moraAlDia) : "—"}
                      </td>
                      <td className="px-3 py-2"><Pill tono={TONO_ESTADO[c.estado] || "neutral"}>{c.estado}</Pill></td>
                    </tr>
                    {detalle[c.id] && (
                      <tr>
                        <td colSpan={9} className="p-0">
                          <ContratoServicing c={detalle[c.id]} onChange={alCambiar} onReload={refrescar}
                                             soloLectura={soloLectura} />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ))}
    </>
  );
}
