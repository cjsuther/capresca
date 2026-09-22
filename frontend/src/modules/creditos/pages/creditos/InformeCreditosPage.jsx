import { useEffect, useState } from "react";
import { creditos } from "../../../../api/creditos";
import { DataTable } from "../../components/DataTable";
import { PageHeader, Card, Field, Boton, Alerta } from "../../components/ui";
import { money, fecha, num } from "../../components/format";

const LIMIT = 25;
const ESTADO = { A: "Activo", C: "Cancelado" };
const VACIO = { estado: "", linea_id: "", cartera: "", organismo_id: "", desde: "", hasta: "", con_saldo: "", q: "" };

const COLS = [
  { key: "credito_id", label: "Crédito", sortable: true },
  { key: "cliente", label: "Cliente", sortable: true },
  { key: "cuil", label: "CUIL" },
  { key: "linea", label: "Línea" },
  { key: "fecha_otorgamiento", label: "Otorgado", sortable: true, render: (c) => fecha(c.fecha_otorgamiento) },
  { key: "capital", label: "Capital", sortable: true, align: "right", render: (c) => money(c.capital) },
  { key: "saldo", label: "Saldo", sortable: true, align: "right", render: (c) => money(c.saldo) },
  { key: "estado", label: "Estado", render: (c) => ESTADO[c.estado] || c.estado },
];

const params = (a) => ({
  estado: a.estado || undefined, linea_id: a.linea_id || undefined,
  cartera: a.cartera || undefined, organismo_id: a.organismo_id || undefined,
  desde: a.desde || undefined, hasta: a.hasta || undefined,
  con_saldo: a.con_saldo || undefined, q: a.q || undefined,
});

export default function InformeCreditosPage() {
  const [f, setF] = useState(VACIO);
  const [aplicado, setAplicado] = useState(VACIO);
  const [lineas, setLineas] = useState([]);
  const [carteras, setCarteras] = useState([]);
  const [organismos, setOrganismos] = useState([]);
  const [data, setData] = useState({ items: [], total: 0, total_capital: 0, total_saldo: 0 });
  const [offset, setOffset] = useState(0);
  const [sort, setSort] = useState("credito_id");
  const [order, setOrder] = useState("desc");
  const [error, setError] = useState("");

  useEffect(() => {
    creditos.lineas().then(setLineas).catch(() => setLineas([]));
    creditos.situacionPorCartera().then((d) => setCarteras(d.por_cartera)).catch(() => setCarteras([]));
    creditos.adminOrganismos().then(setOrganismos).catch(() => setOrganismos([]));
  }, []);

  async function cargar(off = 0, a = aplicado, s = sort, o = order) {
    setError("");
    try {
      const d = await creditos.informeCreditos({ ...params(a), limit: LIMIT, offset: off, sort: s, order: o });
      setData(d); setOffset(off); setSort(s); setOrder(o);
    } catch (e) { setError(e.message); }
  }
  useEffect(() => { cargar(0, aplicado); }, [aplicado]);

  const onSort = (key) => cargar(0, aplicado, key, sort === key && order === "asc" ? "desc" : "asc");
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  return (
    <>
      <PageHeader
        titulo="Informe de créditos"
        descripcion="Generador de informes: combiná estado, línea, cartera, organismo, fechas y saldo."
      >
        <Boton variante="ok" onClick={() => creditos.descargarInformeCreditosExcel({ ...params(aplicado), sort, order })}>
          Descargar Excel
        </Boton>
      </PageHeader>

      {error && <div className="mb-4"><Alerta>{error}</Alerta></div>}

      <Card className="mb-4">
        <div className="grid gap-3 sm:grid-cols-3">
          <Field label="Estado">
            <select className="input w-full" value={f.estado} onChange={set("estado")}>
              <option value="">Todos</option><option value="A">Activos</option><option value="C">Cancelados</option>
            </select>
          </Field>
          <Field label="Línea">
            <select className="input w-full" value={f.linea_id} onChange={set("linea_id")}>
              <option value="">Todas</option>
              {lineas.map((l) => <option key={l.id} value={l.id}>{l.nombre}</option>)}
            </select>
          </Field>
          <Field label="Cartera">
            <select className="input w-full" value={f.cartera} onChange={set("cartera")}>
              <option value="">Todas</option>
              {carteras.map((c) => <option key={c.cartera} value={c.cartera}>{c.nombre}</option>)}
            </select>
          </Field>
          <Field label="Organismo">
            <select className="input w-full" value={f.organismo_id} onChange={set("organismo_id")}>
              <option value="">Todos</option>
              {organismos.map((o) => <option key={o.id} value={o.id}>{o.nombre}</option>)}
            </select>
          </Field>
          <Field label="Saldo">
            <select className="input w-full" value={f.con_saldo} onChange={set("con_saldo")}>
              <option value="">Cualquiera</option>
              <option value="true">Con saldo &gt; 0</option>
              <option value="false">Sin saldo</option>
            </select>
          </Field>
          <Field label="Buscar cliente / CUIL">
            <input className="input w-full" value={f.q} onChange={set("q")} />
          </Field>
          <Field label="Otorgado desde">
            <input type="date" className="input w-full" value={f.desde} onChange={set("desde")} />
          </Field>
          <Field label="Otorgado hasta">
            <input type="date" className="input w-full" value={f.hasta} onChange={set("hasta")} />
          </Field>
          <div className="flex items-end gap-2">
            <Boton onClick={() => setAplicado({ ...f })}>Generar</Boton>
            <Boton variante="secundario" onClick={() => { setF(VACIO); setAplicado(VACIO); }}>Limpiar</Boton>
          </div>
        </div>
      </Card>

      <Card padding={false}>
        <p className="px-4 py-3 text-sm text-gray-500 border-b border-gray-200">
          <b className="text-gray-800">{num(data.total)}</b> créditos · capital {money(data.total_capital || 0)} ·
          saldo {money(data.total_saldo || 0)}
        </p>
        <div className="p-4">
          <DataTable columns={COLS} rows={data.items} total={data.total} limit={LIMIT} offset={offset}
                     sort={sort} order={order} onSort={onSort} onPage={(off) => cargar(off)}
                     rowKey={(c) => c.credito_id} emptyText="Sin créditos para los filtros" />
        </div>
      </Card>
    </>
  );
}
