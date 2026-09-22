import { useState } from "react";
import { creditos } from "../../../../api/creditos";
import { PageHeader, Card, Toolbar, Field, Boton, Alerta } from "../../components/ui";
import { Confirmacion } from "../../components/Confirmacion";
import { usePuedeEscribir } from "../../permisos";
import { money } from "../../components/format";

/**
 * Baja / anulación administrativa de un crédito (cargado por error), con motivo obligatorio.
 * No aplica a créditos con cuotas pagadas: para ésos va la cancelación.
 */
export default function BajaCreditoPage() {
  const puedeEscribir = usePuedeEscribir();
  const [creditoId, setCreditoId] = useState("");
  const [motivo, setMotivo] = useState("");
  const [credito, setCredito] = useState(null);
  const [ok, setOk] = useState(null);
  const [error, setError] = useState("");
  const [confirmando, setConfirmando] = useState(false);
  const [ocupado, setOcupado] = useState(false);

  async function buscar(e) {
    e?.preventDefault();
    setError(""); setOk(null); setCredito(null);
    const id = Number(creditoId);
    if (!id) { setError("Ingresá un número de crédito."); return; }
    try { setCredito(await creditos.credito(id)); }
    catch (err) { setError(err.message); }
  }

  async function darBaja() {
    setError(""); setOcupado(true);
    try {
      setOk(await creditos.bajaCredito(Number(creditoId), motivo.trim()));
      setCredito(null); setMotivo("");
    } catch (err) { setError(err.message); }
    finally { setOcupado(false); setConfirmando(false); }
  }

  return (
    <>
      <PageHeader
        titulo="Baja de crédito"
        descripcion="Anulación administrativa de un crédito con motivo obligatorio. Los créditos con cuotas pagadas se cancelan, no se dan de baja."
      />

      {error && <div className="mb-4"><Alerta>{error}</Alerta></div>}
      {ok && (
        <div className="mb-4">
          <Alerta tipo="ok">Crédito <b>{ok.id}</b> dado de baja (estado {ok.estado}).</Alerta>
        </div>
      )}

      <Card padding={false} className="mb-4">
        <Toolbar>
          <form onSubmit={buscar} className="flex items-end gap-2">
            <Field label="N° de crédito">
              <input className="input w-40" value={creditoId} onChange={(e) => setCreditoId(e.target.value)} />
            </Field>
            <Boton type="submit">Buscar</Boton>
          </form>
        </Toolbar>
      </Card>

      {credito && (
        <Card>
          <h2 className="font-semibold text-gray-800">Crédito {credito.id} — estado {credito.estado}</h2>
          <p className="text-sm text-gray-500 mt-1">
            Capital {money(credito.capital)} · Saldo {money(credito.saldo_capital)}
          </p>
          <div className="mt-4 max-w-xl">
            <Field label="Motivo de baja">
              <input className="input w-full" value={motivo} placeholder="Ej: cargado por error"
                     onChange={(e) => setMotivo(e.target.value)} />
            </Field>
          </div>
          {puedeEscribir ? (
            <Boton variante="danger" className="mt-4" disabled={!motivo.trim()} onClick={() => setConfirmando(true)}>
              Dar de baja el crédito
            </Boton>
          ) : (
            <p className="mt-4 text-sm text-gray-500">Tu usuario sólo puede consultar créditos.</p>
          )}
        </Card>
      )}

      {confirmando && (
        <Confirmacion
          titulo="Dar de baja el crédito"
          mensaje={`Se va a anular el crédito ${creditoId}. La baja no se puede deshacer.\nMotivo: ${motivo.trim()}`}
          confirmar="Dar de baja"
          ocupado={ocupado}
          onConfirmar={darBaja}
          onCancelar={() => setConfirmando(false)}
        />
      )}
    </>
  );
}
