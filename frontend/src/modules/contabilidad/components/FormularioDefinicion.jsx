import { useEffect, useState } from "react";
import {
  crearDefinicion, editarDefinicion, listarCuentas, listarDiarios, mensajeDeError, probarDefinicion,
} from "../../../api/contabilidad";
import { Alerta, Boton, Field, Modal } from "../../../components/ui";
import { money } from "../formato";

const VACIA = { dc: "DEBE", cuenta: "", importe: "", detalle: "" };

/**
 * Cómo se contabiliza un tipo de transacción: qué cuenta va al debe, cuál al haber y cómo se calcula
 * cada importe con los campos que manda el módulo.
 *
 * Sirve para las tres situaciones: definir la regla que falta (desde una transacción pendiente),
 * crear una nueva desde cero y editar una existente.
 */
export function FormularioDefinicion({ definicion, pendiente, onCerrar, onListo }) {
  const editando = !!definicion?.id;
  const base = definicion || {};
  pendiente = pendiente?.nueva ? null : pendiente;
  const tipoSugerido = pendiente?.tipo || base.tipo || "";

  const [modulo, setModulo] = useState(pendiente?.modulo || base.modulo || "");
  const [tipo, setTipo] = useState(tipoSugerido);
  const [nombre, setNombre] = useState(base.nombre || tipoSugerido.replaceAll("_", " ").toLowerCase());
  const [diario, setDiario] = useState(base.diario || "VAR");
  const [leyenda, setLeyenda] = useState(base.leyenda || (tipoSugerido ? `${tipoSugerido} {referencia}` : ""));
  const [activa, setActiva] = useState(base.activa !== false);
  const [lineas, setLineas] = useState(
    base.lineas?.length ? base.lineas.map((l) => ({ ...VACIA, ...l })) : [{ ...VACIA }, { ...VACIA, dc: "HABER" }]);
  const [cuentas, setCuentas] = useState([]);
  const [diarios, setDiarios] = useState([]);
  const [error, setError] = useState("");
  const [previa, setPrevia] = useState(null);
  const [guardando, setGuardando] = useState(false);

  // Campos disponibles: los que manda el módulo en esa transacción (si venimos de una pendiente).
  const ejemplo = pendiente?.ejemplo?.datos || {};
  const campos = pendiente?.campos || Object.keys(ejemplo);

  useEffect(() => {
    listarCuentas({ solo_imputables: true }).then((d) => setCuentas(d.items)).catch(() => {});
    listarDiarios().then((d) => setDiarios(d.items)).catch(() => {});
  }, []);

  const cambiar = (i, campo, v) => setLineas((ls) => ls.map((l, j) => (j === i ? { ...l, [campo]: v } : l)));
  const completas = lineas.filter((l) => l.cuenta && String(l.importe).trim());
  const puedeGuardar = modulo.trim() && tipo.trim() && completas.length >= 2;

  // Sin nombre propio, se usa el del tipo de transacción (que es lo que se lee en el listado).
  const payload = () => ({
    modulo: modulo.trim(), tipo: tipo.trim().toUpperCase(),
    nombre: nombre.trim() || tipo.trim().replaceAll("_", " ").toLowerCase(),
    diario_codigo: diario, leyenda, activa, lineas: completas,
  });

  const guardar = async () => {
    setError(""); setPrevia(null); setGuardando(true);
    try {
      const d = editando ? await editarDefinicion(definicion.id, payload()) : await crearDefinicion(payload());
      onListo(d);
    } catch (e) {
      setError(mensajeDeError(e, "No se pudo guardar la definición"));
    } finally {
      setGuardando(false);
    }
  };

  const probar = async () => {
    setError(""); setPrevia(null);
    if (!editando) { setError("Guardá la definición para poder probarla con datos reales."); return; }
    try {
      setPrevia(await probarDefinicion(definicion.id, ejemplo));
    } catch (e) { setError(mensajeDeError(e, "La definición no se puede aplicar")); }
  };

  const titulo = editando ? `Definición · ${base.tipo}`
    : pendiente ? `Cómo se contabiliza «${pendiente.tipo}»` : "Nueva definición de asiento";
  const eyebrow = pendiente ? `${pendiente.modulo} · ${pendiente.cantidad} transacción(es) esperando`
    : editando ? base.modulo : "Contabilidad";

  return (
    <Modal titulo={titulo} eyebrow={eyebrow} onClose={onCerrar} ancho="max-w-4xl"
           footer={<>
             <span className="text-xs text-gray-500 mr-auto">
               Al guardar se contabilizan las transacciones de este tipo que estaban esperando.
             </span>
             {editando && <Boton variante="secundario" onClick={probar}>Probar</Boton>}
             <Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton>
             <Boton disabled={guardando || !puedeGuardar} onClick={guardar}>
               {guardando ? "Guardando…" : "Guardar y contabilizar"}
             </Boton>
           </>}>
      <div className="space-y-4">
        {error && <Alerta>{error}</Alerta>}

        {campos.length > 0 && (
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-3">
            <p className="text-xs text-gray-500 mb-1">
              Campos que manda {pendiente?.modulo || modulo || "el módulo"} (usalos en los importes)
            </p>
            <div className="flex flex-wrap gap-2">
              {campos.map((c) => (
                <code key={c} className="text-xs bg-surface border border-gray-200 rounded px-2 py-0.5">
                  {c}{ejemplo[c] !== undefined ? ` = ${ejemplo[c]}` : ""}
                </code>
              ))}
            </div>
          </div>
        )}

        <div className="grid sm:grid-cols-3 gap-3">
          <Field label="Módulo">
            <input className="input w-full" value={modulo} disabled={editando || !!pendiente}
                   placeholder="creditos, tesoreria…" onChange={(e) => setModulo(e.target.value)} />
          </Field>
          <Field label="Tipo de transacción">
            <input className="input w-full" value={tipo} disabled={editando || !!pendiente}
                   placeholder="DESEMBOLSO" onChange={(e) => setTipo(e.target.value)} />
          </Field>
          <Field label="Nombre">
            <input className="input w-full" value={nombre} placeholder={tipo.replaceAll("_", " ").toLowerCase()}
                   onChange={(e) => setNombre(e.target.value)} />
          </Field>
          <Field label="Diario">
            <select className="input w-full" value={diario} onChange={(e) => setDiario(e.target.value)}>
              {diarios.map((d) => <option key={d.codigo} value={d.codigo}>{d.nombre}</option>)}
            </select>
          </Field>
          <Field label="Leyenda del asiento" className="sm:col-span-2">
            <input className="input w-full" value={leyenda} onChange={(e) => setLeyenda(e.target.value)}
                   placeholder="Desembolso {referencia}" />
          </Field>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[720px]">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50 text-left text-xs text-gray-500">
                <th className="px-3 py-2 font-medium">Lado</th>
                <th className="px-3 py-2 font-medium">Cuenta</th>
                <th className="px-3 py-2 font-medium">Importe</th>
                <th className="px-3 py-2 font-medium">Detalle</th>
                <th className="px-3 py-2" />
              </tr>
            </thead>
            <tbody>
              {lineas.map((l, i) => (
                <tr key={i} className="border-b border-gray-100">
                  <td className="px-3 py-1.5">
                    <select className="input" aria-label={`Lado ${i + 1}`} value={l.dc}
                            onChange={(e) => cambiar(i, "dc", e.target.value)}>
                      <option value="DEBE">Debe</option><option value="HABER">Haber</option>
                    </select>
                  </td>
                  <td className="px-3 py-1.5">
                    <select className="input w-64" aria-label={`Cuenta ${i + 1}`} value={l.cuenta}
                            onChange={(e) => cambiar(i, "cuenta", e.target.value)}>
                      <option value="">(elegir)</option>
                      {cuentas.map((c) => <option key={c.codigo} value={c.codigo}>{c.codigo} · {c.nombre}</option>)}
                    </select>
                  </td>
                  <td className="px-3 py-1.5">
                    <input className="input w-40" aria-label={`Importe ${i + 1}`} value={l.importe}
                           placeholder="capital + iva" onChange={(e) => cambiar(i, "importe", e.target.value)} />
                  </td>
                  <td className="px-3 py-1.5">
                    <input className="input w-full" aria-label={`Detalle ${i + 1}`} value={l.detalle || ""}
                           onChange={(e) => cambiar(i, "detalle", e.target.value)} />
                  </td>
                  <td className="px-3 py-1.5 text-right">
                    <button type="button" aria-label={`Quitar línea ${i + 1}`} className="text-gray-400 hover:text-red-600"
                            onClick={() => setLineas((ls) => (ls.length > 2 ? ls.filter((_, j) => j !== i) : ls))}>✕</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <Boton type="button" variante="secundario" onClick={() => setLineas((ls) => [...ls, { ...VACIA }])}>
            ＋ Agregar línea
          </Boton>
          <label className="flex items-center gap-2 text-sm text-gray-600">
            <input type="checkbox" checked={activa} onChange={(e) => setActiva(e.target.checked)} /> Activa
          </label>
        </div>

        {previa && (
          <div className="border border-green-200 bg-green-50 rounded-lg p-3">
            <p className="text-sm font-medium text-green-800 mb-1">Así queda el asiento con estos datos</p>
            <ul className="text-sm text-gray-700">
              {previa.lineas.map((l, i) => (
                <li key={i} className="tabular-nums">
                  {l.cuenta} {l.nombre} · {l.debe ? `debe ${money(l.debe)}` : `haber ${money(l.haber)}`}
                </li>
              ))}
            </ul>
            <p className="text-xs text-gray-600 mt-1">Total debe {money(previa.debe)} · haber {money(previa.haber)}</p>
          </div>
        )}
      </div>
    </Modal>
  );
}
