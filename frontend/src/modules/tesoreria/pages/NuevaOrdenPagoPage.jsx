import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowLeft, FileCheck2 } from "lucide-react";
import { actosDisponibles, confeccionarOrden, mensajeDeError } from "../../../api/tesoreria";
import { Alerta, Boton, Card, PageHeader } from "../../../components/ui";
import { Confirmacion } from "../../../components/ui/Confirmacion";
import { fechaHora, money, textoActo } from "../estados";

const fecha = (f) => (f ? new Date(`${String(f).slice(0, 10)}T00:00:00`).toLocaleDateString("es-AR") : "");

/**
 * Confección de una orden de pago: se eligen resoluciones / disposiciones y entran completos sus lotes de
 * créditos que no están en otra orden. Sólo las que ya tienen N° oficial (una en borrador no se paga).
 */
export default function NuevaOrdenPagoPage() {
  const navigate = useNavigate();
  const [grupos, setGrupos] = useState(null);
  const [elegidos, setElegidos] = useState(() => new Set());
  const [error, setError] = useState("");
  const [confirmando, setConfirmando] = useState(false);
  const [ocupado, setOcupado] = useState(false);

  useEffect(() => {
    actosDisponibles()
      .then((d) => setGrupos(d.items))
      .catch((e) => { setGrupos([]); setError(mensajeDeError(e, "No se pudieron traer las resoluciones de Créditos")); });
  }, []);

  const marcar = (clave) => setElegidos((s) => {
    const n = new Set(s);
    n.has(clave) ? n.delete(clave) : n.add(clave);
    return n;
  });
  const sel = (grupos || []).filter((g) => elegidos.has(g.acto.clave));
  const total = sel.reduce((a, g) => a + Number(g.total || 0), 0);
  const cantidad = sel.reduce((a, g) => a + Number(g.cantidad || 0), 0);

  const confeccionar = async () => {
    setOcupado(true); setError("");
    try {
      const op = await confeccionarOrden([...elegidos]);
      navigate(`/modules/tesoreria/ordenes/${op.id}`);
    } catch (e) {
      setError(mensajeDeError(e, "No se pudo confeccionar la orden de pago"));
      setConfirmando(false);
    } finally {
      setOcupado(false);
    }
  };

  return (
    <div className="space-y-4">
      <Link to="/modules/tesoreria/ordenes" className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700">
        <ArrowLeft size={14} /> Órdenes de pago
      </Link>
      <PageHeader titulo="Nueva orden de pago"
                  descripcion="Elegí las resoluciones o disposiciones a pagar. Entran todos sus lotes de créditos que no estén en otra orden; se originan los créditos y los lotes quedan para liquidar." />
      <Alerta>{error}</Alerta>

      {grupos === null && <p className="text-sm text-gray-400">Cargando…</p>}
      {grupos && grupos.length === 0 && !error && (
        <Card><p className="text-sm text-gray-500">No hay resoluciones ni disposiciones con lotes para pagar.</p></Card>
      )}

      {(grupos || []).map((g) => {
        const sinOficial = !g.acto.numeroOficial;
        return (
          <Card key={g.acto.clave}>
            <label className={`flex items-start gap-3 ${sinOficial ? "opacity-60" : "cursor-pointer"}`}>
              <input type="checkbox" className="mt-1" aria-label={`Elegir ${textoActo(g.acto)}`} disabled={sinOficial}
                     checked={elegidos.has(g.acto.clave)} onChange={() => marcar(g.acto.clave)} />
              <div className="flex-1">
                <p className="font-medium text-gray-800">
                  {textoActo(g.acto)}{g.acto.fecha ? <span className="text-gray-500 font-normal"> · {fecha(g.acto.fecha)}</span> : null}
                </p>
                <p className="text-sm text-gray-500">
                  {g.lotes.length} lote(s) · {g.cantidad} crédito(s) · {money(g.total)}
                  {g.acto.importe != null && <> · importe de la resolución {money(g.acto.importe)}</>}
                </p>
                {sinOficial && <p className="text-xs text-red-600 mt-1">Todavía no tiene N° oficial: no se paga en borrador.</p>}
                <ul className="mt-2 text-sm text-gray-600 space-y-0.5">
                  {g.lotes.map((l) => (
                    <li key={l.id} className="tabular-nums">
                      Lote {l.codigo} · {l.producto} · {fecha(l.fecha)} · {l.cantidad} solicitud(es) · {money(l.montoTotal)}
                      {l.cerradoPor && <span className="text-gray-400"> · cerrado por {l.cerradoPor} {fechaHora(l.cerradoEn)}</span>}
                    </li>
                  ))}
                </ul>
              </div>
            </label>
          </Card>
        );
      })}

      {elegidos.size > 0 && (
        <div className="flex flex-wrap items-center justify-end gap-3">
          <p className="text-sm text-gray-600">
            {elegidos.size} acto(s) · {cantidad} transferencia(s) · <b className="tabular-nums">{money(total)}</b>
          </p>
          <Boton onClick={() => setConfirmando(true)} disabled={ocupado} className="flex items-center gap-2">
            <FileCheck2 size={16} /> Confeccionar orden de pago
          </Boton>
        </div>
      )}

      {confirmando && (
        <Confirmacion
          titulo="Confeccionar la orden de pago"
          mensaje={`Se confecciona la orden con ${sel.map((g) => textoActo(g.acto)).join(", ")}: ${cantidad} transferencia(s) por ${money(total)}.\nSe originan los créditos y sus lotes quedan para liquidar. Después la aprueba y la paga el tesorero.`}
          confirmar="Confeccionar"
          danger={false}
          ocupado={ocupado}
          onConfirmar={confeccionar}
          onCancelar={() => setConfirmando(false)}
        />
      )}
    </div>
  );
}
