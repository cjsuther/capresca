import { useEffect, useState } from "react";
import { api } from "../../api";
import DataTable, { Col } from "../../components/DataTable";

const pct = (v: string | number) => `${Number(v).toLocaleString("es-AR", { minimumFractionDigits: 2 })} %`;

const COLS: Col[] = [
  { key: "codigo", label: "Código", sortable: true },
  { key: "modalidad", label: "Mod.", sortable: true },
  { key: "cod_afip", label: "Cód. AFIP", sortable: true },
  { key: "denominacion", label: "Denominación", sortable: true },
  { key: "com_agencia", label: "Com. agencia", sortable: true, align: "right", sortValue: (j) => Number(j.com_agencia), render: (j) => pct(j.com_agencia) },
  { key: "com_subagencia", label: "Com. subagencia", sortable: true, align: "right", sortValue: (j) => Number(j.com_subagencia), render: (j) => pct(j.com_subagencia) },
];

export default function MaestroJuegos() {
  const [juegos, setJuegos] = useState<any[]>([]);
  useEffect(() => { api.maestroJuegos().then(setJuegos); }, []);

  return (
    <div className="card">
      <h2 style={{ marginTop: 0 }}>Maestro de juegos</h2>
      <p className="muted">Juegos y modalidades habilitados, con la comisión de agencia y subagencia. Fuente: maejuegos.</p>
      <DataTable columns={COLS} rows={juegos} rowKey={(j) => j.id}
                 clientSort pageSize={25} defaultSort="codigo" emptyText="Sin juegos cargados" />
    </div>
  );
}
