import { useState } from "react";
import { Modal, Field, Boton } from "./ui";

/**
 * Pide un importe o una cantidad antes de ejecutar una operación (pago parcial, prepago, diferir…).
 * `children` permite agregar opciones extra al pedido (p.ej. cómo aplicar el prepago).
 */
export function PedirNumero({ titulo, etiqueta, boton = "Aceptar", ayuda, children, onConfirmar, onCancelar }) {
  const [valor, setValor] = useState("");
  return (
    <Modal
      titulo={titulo}
      ancho="max-w-md"
      onClose={onCancelar}
      footer={
        <>
          <span className="flex-1" />
          <Boton variante="secundario" onClick={onCancelar}>Cancelar</Boton>
          <Boton disabled={!Number(valor)} onClick={() => onConfirmar(Number(valor))}>{boton}</Boton>
        </>
      }
    >
      {ayuda && <p className="text-sm text-gray-500 mb-3">{ayuda}</p>}
      <Field label={etiqueta}>
        <input type="number" className="input w-full" value={valor} autoFocus
               onChange={(e) => setValor(e.target.value)} />
      </Field>
      {children}
    </Modal>
  );
}
