import { useEffect, useState } from "react";
import { creditos } from "../../../../api/creditos";
import { DataTable } from "../../components/DataTable";
import { PageHeader, Card, Toolbar, Field, Boton, LimpiarFiltros, Alerta } from "../../components/ui";
import { money, fecha, num } from "../../components/format";

const LIMIT = 25;

const COLS = [
  { key: "fecha", label: "Fecha", render: (t) => fecha(t.fecha) },
  { key: "periodo", label: "Período" },
  { key: "tipo", label: "Tipo" },
  { key: "numero", label: "N° turno" },
  { key: "apellido_nombre", label: "Solicitante" },
  { key: "cuil", label: "CUIL" },
  { key: "sueldo", label: "Sueldo", align: "right", render: (t) => money(t.sueldo) },
  { key: "usado", label: "Usado", render: (t) => (t.usado ? "Sí" : "—") },
  { key: "autorizado", label: "Autorizado", render: (t) => (t.autorizado ? "Sí" : "—") },
];

export default function TurnosOtorgadosPage() {
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [busq, setBusq] = useState("");
  const [q, setQ] = useState("");
  const [tipo, setTipo] = useState("");
  const [usado, setUsado] = useState("");
  const [error, setError] = useState("");

  const filtros = () => ({
    q: q || undefined, tipo: tipo || undefined,
    usado: usado === "" ? undefined : usado === "si",
  });

  async function cargar(off = 0) {
    setError("");
    try {
      const d = await creditos.turnosOtorgados({ ...filtros(), limit: LIMIT, offset: off });
      setRows(d.items); setTotal(d.total); setOffset(off);
    } catch (e) { setError(e.message); }
  }
  useEffect(() => { cargar(0); }, [q, tipo, usado]);

  return (
    <>
      <PageHeader
        titulo="Turnos otorgados"
        descripcion="Turnos para presentar la solicitud de crédito, con su estado de uso y autorización."
      />

      {error && <div className="mb-4"><Alerta>{error}</Alerta></div>}

      <Card padding={false}>
        <Toolbar>
          <form onSubmit={(e) => { e.preventDefault(); setQ(busq); }} className="flex items-end gap-2">
            <input className="input w-64" value={busq} onChange={(e) => setBusq(e.target.value)}
                   placeholder="Buscar solicitante / CUIL" />
            <button type="submit" className="px-3 py-2 text-sm border rounded-lg text-gray-600 hover:bg-gray-50">Buscar</button>
          </form>
          <Field label="Tipo">
            <select className="input" value={tipo} onChange={(e) => setTipo(e.target.value)}>
              <option value="">Todo tipo</option><option value="TODO">TODO</option><option value="AGAP">AGAP</option>
            </select>
          </Field>
          <Field label="Uso">
            <select className="input" value={usado} onChange={(e) => setUsado(e.target.value)}>
              <option value="">Usados y no usados</option>
              <option value="si">Usados</option>
              <option value="no">No usados</option>
            </select>
          </Field>
          <LimpiarFiltros activo={!!q || !!busq || !!tipo || usado !== ""}
                          onClear={() => { setBusq(""); setQ(""); setTipo(""); setUsado(""); }} />
          <Boton variante="ok" onClick={() => creditos.descargarTurnosExcel(filtros())}>Excel</Boton>
          <span className="ml-auto text-sm text-gray-500">{num(total)} turnos</span>
        </Toolbar>
        <div className="p-4">
          <DataTable columns={COLS} rows={rows} total={total} limit={LIMIT} offset={offset}
                     onPage={(off) => cargar(off)}
                     rowKey={(t, i) => `${t.periodo}-${t.tipo}-${t.numero}-${i}`}
                     emptyText="Sin turnos" />
        </div>
      </Card>
    </>
  );
}
