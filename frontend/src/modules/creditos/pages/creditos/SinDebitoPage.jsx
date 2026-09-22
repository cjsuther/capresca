import { useEffect, useState } from "react";
import { creditos } from "../../../../api/creditos";
import { DataTable } from "../../components/DataTable";
import { PageHeader, Card, Toolbar, Field, LimpiarFiltros, Alerta } from "../../components/ui";
import { money, num } from "../../components/format";

const LIMIT = 25;

const COLS = [
  { key: "credito_id", label: "Crédito" },
  { key: "cliente", label: "Cliente" },
  { key: "cuil", label: "CUIL" },
  { key: "linea", label: "Línea" },
  { key: "sueldo", label: "Sueldo", align: "right", render: (r) => money(r.sueldo) },
  { key: "saldo", label: "Saldo", align: "right", render: (r) => money(r.saldo) },
];

export default function SinDebitoPage() {
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [saldo, setSaldo] = useState(0);
  const [offset, setOffset] = useState(0);
  const [busq, setBusq] = useState("");
  const [q, setQ] = useState("");
  const [lineas, setLineas] = useState([]);
  const [lineaId, setLineaId] = useState("");
  const [error, setError] = useState("");

  useEffect(() => { creditos.lineas().then(setLineas).catch(() => setLineas([])); }, []);

  async function cargar(off = 0, query = q, linea = lineaId) {
    setError("");
    try {
      const d = await creditos.creditosSinDebito({
        q: query || undefined, linea_id: linea ? Number(linea) : undefined,
        limit: LIMIT, offset: off,
      });
      setRows(d.items); setTotal(d.total); setSaldo(d.total_saldo); setOffset(off);
    } catch (e) { setError(e.message); }
  }
  useEffect(() => { cargar(0, q, lineaId); }, [q, lineaId]);

  return (
    <>
      <PageHeader
        titulo="Créditos sin débito automático"
        descripcion="Créditos activos cuyo cliente no tiene CBU cargado: se cobran a mano, no entran al padrón de débito."
      />

      {error && <div className="mb-4"><Alerta>{error}</Alerta></div>}

      <Card padding={false}>
        <Toolbar>
          <form onSubmit={(e) => { e.preventDefault(); setQ(busq); }} className="flex items-end gap-2">
            <input className="input w-64" value={busq} onChange={(e) => setBusq(e.target.value)}
                   placeholder="Buscar cliente / CUIL" />
            <button type="submit" className="px-3 py-2 text-sm border rounded-lg text-gray-600 hover:bg-gray-50">Buscar</button>
          </form>
          <Field label="Línea">
            <select className="input max-w-[220px]" value={lineaId} onChange={(e) => setLineaId(e.target.value)}>
              <option value="">Todas las líneas</option>
              {lineas.map((l) => <option key={l.id} value={l.id}>{l.nombre}</option>)}
            </select>
          </Field>
          <LimpiarFiltros activo={!!q || !!busq || !!lineaId}
                          onClear={() => { setBusq(""); setQ(""); setLineaId(""); }} />
          <span className="ml-auto text-sm text-gray-500">
            {num(total)} créditos · saldo <b>{money(saldo || 0)}</b>
          </span>
        </Toolbar>
        <div className="p-4">
          <DataTable columns={COLS} rows={rows} total={total} limit={LIMIT} offset={offset}
                     onPage={(off) => cargar(off)} rowKey={(r) => r.credito_id} emptyText="Sin resultados" />
        </div>
      </Card>
    </>
  );
}
