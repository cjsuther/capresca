import { useState } from "react";
import { creditos } from "../../../../api/creditos";
import { DataTable } from "../../components/DataTable";
import { PageHeader, Card, Toolbar, Field, Boton, Alerta } from "../../components/ui";
import { Confirmacion } from "../../components/Confirmacion";
import { usePuedeEscribir } from "../../permisos";
import { fecha, num } from "../../components/format";

/**
 * Turnos de crédito: generación del mes distribuida por día hábil (con vista previa) y asignación
 * de un turno a un solicitante. No hay tabla de feriados migrada: se excluyen fines de semana.
 */
const periodoProximoMes = () => {
  const h = new Date();
  return `${h.getFullYear()}${String(h.getMonth() + 2).padStart(2, "0")}`;
};

export default function TurnosAdminPage() {
  const puedeEscribir = usePuedeEscribir();
  const [periodo, setPeriodo] = useState(periodoProximoMes());
  const [cantidad, setCantidad] = useState("100");
  const [prev, setPrev] = useState(null);
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");
  const [confirmando, setConfirmando] = useState(false);
  const [ocupado, setOcupado] = useState(false);

  const [cuil, setCuil] = useState("");
  const [nombre, setNombre] = useState("");
  const [numero, setNumero] = useState("");

  async function previsualizar(e) {
    e?.preventDefault();
    setError(""); setMsg(""); setPrev(null);
    try { setPrev(await creditos.turnosPreview(periodo, Number(cantidad))); }
    catch (err) { setError(err.message); }
  }

  async function generar() {
    setError(""); setOcupado(true);
    try {
      const r = await creditos.turnosGenerar({ periodo, cantidad: Number(cantidad) });
      setMsg(`Generados ${num(r.generados)} turnos del período ${r.periodo}.`);
      setPrev(null);
    } catch (err) { setError(err.message); }
    finally { setOcupado(false); setConfirmando(false); }
  }

  async function asignar(e) {
    e?.preventDefault();
    setError(""); setMsg("");
    try {
      const r = await creditos.turnoAsignar({
        periodo, cuil, apellido_nombre: nombre,
        numero: numero ? Number(numero) : undefined,
      });
      setMsg(`Turno N° ${r.numero} (${fecha(r.fecha)}) asignado a ${r.apellido_nombre || r.cuil}.`);
      setCuil(""); setNombre(""); setNumero("");
    } catch (err) { setError(err.message); }
  }

  return (
    <>
      <PageHeader
        titulo="Turnos de crédito — administración"
        descripcion="Generación de los turnos del mes distribuidos por día hábil y asignación a solicitantes."
      />

      {error && <div className="mb-4"><Alerta>{error}</Alerta></div>}
      {msg && <div className="mb-4"><Alerta tipo="ok">{msg}</Alerta></div>}

      <Card padding={false} className="mb-4">
        <Toolbar>
          <form onSubmit={previsualizar} className="flex items-end gap-3">
            <Field label="Período (YYYYMM)">
              <input className="input w-32" value={periodo} onChange={(e) => setPeriodo(e.target.value)} />
            </Field>
            <Field label="Cantidad de turnos">
              <input className="input w-32" value={cantidad} onChange={(e) => setCantidad(e.target.value)} />
            </Field>
            <Boton type="submit">Previsualizar distribución</Boton>
          </form>
        </Toolbar>

        {prev && (
          <div className="p-4">
            <p className="text-sm text-gray-600 mb-3">
              Días hábiles: <b>{num(prev.dias_habiles)}</b> · Turnos/día: <b>{num(prev.turnos_por_dia)}</b> ·
              {" "}Resto: <b>{num(prev.resto)}</b> · Total: <b>{num(prev.total)}</b>
            </p>
            {prev.ya_existen > 0 && (
              <div className="mb-3">
                <Alerta tipo="warn">Ya existen {num(prev.ya_existen)} turnos de este período: no se generan de nuevo.</Alerta>
              </div>
            )}
            <DataTable
              columns={[
                { key: "fecha", label: "Fecha", render: (d) => fecha(d.fecha) },
                { key: "cantidad", label: "Turnos", align: "right" },
              ]}
              rows={prev.distribucion} rowKey={(d, i) => i} pageSize={12}
              emptyText="El período no tiene días hábiles"
            />
            {puedeEscribir && (
              <Boton className="mt-3" disabled={prev.ya_existen > 0} onClick={() => setConfirmando(true)}>
                Confirmar y generar
              </Boton>
            )}
          </div>
        )}
      </Card>

      {puedeEscribir && (
        <Card>
          <h2 className="font-semibold text-gray-800 mb-3">Asignar turno a un solicitante</h2>
          <form onSubmit={asignar} className="flex flex-wrap items-end gap-3">
            <Field label="Período">
              <input className="input w-28" value={periodo} onChange={(e) => setPeriodo(e.target.value)} />
            </Field>
            <Field label="CUIL">
              <input className="input w-40" value={cuil} onChange={(e) => setCuil(e.target.value)} />
            </Field>
            <Field label="Apellido y nombre">
              <input className="input w-56" value={nombre} onChange={(e) => setNombre(e.target.value)} />
            </Field>
            <Field label="N° (excepcional, opcional)">
              <input className="input w-36" value={numero} placeholder="próximo libre"
                     onChange={(e) => setNumero(e.target.value)} />
            </Field>
            <Boton type="submit" disabled={!cuil}>Asignar turno</Boton>
          </form>
        </Card>
      )}

      {confirmando && (
        <Confirmacion
          titulo="Generar los turnos del período"
          mensaje={`Se van a crear ${num(prev?.total)} turnos del período ${periodo}, repartidos en ${num(prev?.dias_habiles)} días hábiles.`}
          confirmar="Generar turnos"
          danger={false}
          ocupado={ocupado}
          onConfirmar={generar}
          onCancelar={() => setConfirmando(false)}
        />
      )}
    </>
  );
}
