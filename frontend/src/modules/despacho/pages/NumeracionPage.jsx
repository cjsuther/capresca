import { useCallback, useEffect, useState } from "react";

import { fijarNumeracion, getNumeracion } from "../../../api/despacho";
import { Alerta, Boton, Card, PageHeader } from "../../../components/ui";
import { useHasPermission } from "../../../context/usePermissions";

const ANIO = new Date().getFullYear();
const entero = (v) => (String(v ?? "").trim() === "" ? null : Math.floor(Number(v)));
const fechaHora = (iso) => (iso ? new Date(iso).toLocaleString("es-AR", { dateStyle: "short", timeStyle: "short" }) : "");

/** Una serie: lo último usado y los próximos números, editables por quien emite los actos. */
function FilaSerie({ fila, puedeEditar, onGuardada }) {
  const [numero, setNumero] = useState(fila.desdeNumero ?? "");
  const [oficial, setOficial] = useState(fila.desdeOficial ?? "");
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");
  const cambio = entero(numero) !== (fila.desdeNumero ?? null) || entero(oficial) !== (fila.desdeOficial ?? null);

  async function guardar() {
    setGuardando(true); setError("");
    try {
      onGuardada(await fijarNumeracion(fila.anio, fila.serie, { desde_numero: entero(numero), desde_oficial: entero(oficial) }));
    } catch (e) {
      setError(e?.response?.data?.detail || "No se pudo guardar la numeración");
    } finally {
      setGuardando(false);
    }
  }

  const campo = (valor, set, etiqueta, ultimo) => (
    <input type="number" min={(ultimo || 0) + 1} className="input w-28 tabular-nums" aria-label={etiqueta}
           value={valor} disabled={!puedeEditar} placeholder={String((ultimo || 0) + 1)}
           onChange={(e) => set(e.target.value)} />
  );

  return (
    <tr className="align-top">
      <td className="px-3 py-2">
        <p className="font-medium text-gray-800">{fila.serie} · {fila.nombre}</p>
        {fila.actualizadoPor && <p className="text-xs text-gray-400">Fijado por {fila.actualizadoPor} · {fechaHora(fila.actualizadoEn)}</p>}
        {error && <p className="text-xs text-red-600 mt-1">{error}</p>}
      </td>
      <td className="px-3 py-2 text-right tabular-nums text-gray-500">{fila.ultimoNumero ?? "—"}</td>
      <td className="px-3 py-2">
        {campo(numero, setNumero, `Próximo correlativo serie ${fila.serie}`, fila.ultimoNumero)}
        <p className="text-xs text-gray-500 mt-1">Va a ser el <b>{fila.proximoNumero}</b></p>
      </td>
      <td className="px-3 py-2 text-right tabular-nums text-gray-500">{fila.ultimoOficial ?? "—"}</td>
      <td className="px-3 py-2">
        {campo(oficial, setOficial, `Próximo N° oficial serie ${fila.serie}`, fila.ultimoOficial)}
        <p className="text-xs text-gray-500 mt-1">Va a ser el <b>{fila.proximoOficial}</b></p>
      </td>
      <td className="px-3 py-2 text-right">
        {puedeEditar && (
          <Boton variante="secundario" disabled={!cambio || guardando} onClick={guardar}>
            {guardando ? "Guardando…" : "Guardar"}
          </Boton>
        )}
      </td>
    </tr>
  );
}

/**
 * Desde qué número sigue cada serie en el año: la numeración de resoluciones y disposiciones continúa la
 * del sistema anterior. El próximo número nunca queda en uno ya usado.
 */
export default function NumeracionPage() {
  const puedeEditar = useHasPermission("despacho", "resoluciones:firmar");
  const [anio, setAnio] = useState(ANIO);
  const [filas, setFilas] = useState([]);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");

  const cargar = useCallback(() => {
    setError("");
    getNumeracion(anio).then(setFilas)
      .catch((e) => setError(e?.response?.data?.detail || "No se pudo cargar la numeración"));
  }, [anio]);
  useEffect(cargar, [cargar]);

  const guardada = (f) => {
    setFilas((xs) => xs.map((x) => (x.serie === f.serie ? f : x)));
    setOk(`Serie ${f.serie}: el próximo correlativo es el ${f.proximoNumero} y el próximo N° oficial el ${f.proximoOficial}.`);
  };

  return (
    <div className="space-y-4">
      <PageHeader titulo="Numeración"
                  descripcion="Desde qué número siguen el correlativo y el N° oficial de cada serie en el año, para continuar la numeración del sistema anterior.">
        <label className="flex items-center gap-2 text-sm text-gray-600">
          Año
          <select className="input" value={anio} aria-label="Año" onChange={(e) => { setAnio(Number(e.target.value)); setOk(""); }}>
            {[ANIO + 1, ANIO, ANIO - 1].map((a) => <option key={a} value={a}>{a}</option>)}
          </select>
        </label>
      </PageHeader>

      <Alerta>{error}</Alerta>
      {ok && <Alerta tipo="ok">{ok}</Alerta>}
      {!puedeEditar && <Alerta tipo="warn">Sólo quien firma las resoluciones puede cambiar la numeración.</Alerta>}

      <Card padding={false}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
                <th className="px-3 py-2 text-left">Serie</th>
                <th className="px-3 py-2 text-right">Último correlativo</th>
                <th className="px-3 py-2 text-left">Próximo correlativo</th>
                <th className="px-3 py-2 text-right">Último N° oficial</th>
                <th className="px-3 py-2 text-left">Próximo N° oficial</th>
                <th className="px-3 py-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {filas.map((f) => (
                <FilaSerie key={`${f.anio}-${f.serie}-${f.actualizadoEn || ""}`} fila={f} puedeEditar={puedeEditar} onGuardada={guardada} />
              ))}
            </tbody>
          </table>
        </div>
        <p className="px-3 py-2 text-xs text-gray-500 border-t border-gray-100">
          Vacío = sigue desde el último número usado en el año. No se puede fijar un número ya usado: la numeración no vuelve atrás.
        </p>
      </Card>
    </div>
  );
}
