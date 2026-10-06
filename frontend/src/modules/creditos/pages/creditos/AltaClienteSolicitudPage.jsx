import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { creditos } from "../../../../api/creditos";
import { PageHeader, Card, Field, Boton, Alerta } from "../../components/ui";

/** Canal por el que esta solapa avisa a la de Solicitudes que el cliente quedó vinculado. */
export const CANAL_SOLICITUDES = "creditos-solicitudes";

/** Texto de lo que pasó con los adjuntos al crear/vincular el cliente. */
export const resumenDocs = (d) => {
  if (!d) return "";
  if (d.error) return ` ${d.error} Reintentá con "Guardar en el cliente".`;
  if (!d.guardados && !d.repetidos) return "";
  return ` ${d.guardados} documento(s) guardado(s) en su ficha${d.repetidos ? ` (${d.repetidos} ya estaba(n))` : ""}.`;
};

/** URL de esta pantalla: se abre en otra solapa para tener a la vista el detalle y los anexos. */
export const urlAltaCliente = (id) => `/modules/creditos/solicitudes-credito/${id}/alta-cliente`;

function avisar(mensaje) {
  try {
    const c = new BroadcastChannel(CANAL_SOLICITUDES);
    c.postMessage(mensaje);
    c.close();
  } catch { /* sin BroadcastChannel: la otra solapa se entera al recargar */ }
}

const CAMPOS = [["apellido", "Apellido"], ["nombres", "Nombres"], ["dni", "DNI"], ["cuil", "CUIL"],
                ["email", "Email"], ["telefono", "Teléfono"], ["domicilio", "Domicilio"], ["localidad", "Localidad"]];

/** Alta en el módulo Clientes con lo que trajo la solicitud; el asesor completa lo que falte. */
export default function AltaClienteSolicitudPage() {
  const { id } = useParams();
  const [sol, setSol] = useState(null);
  const [docs, setDocs] = useState([]);
  const [form, setForm] = useState(null);
  const [error, setError] = useState("");
  const [creando, setCreando] = useState(false);
  const [hecho, setHecho] = useState(null);   // { texto, clienteId }

  useEffect(() => {
    creditos.ppSolicitud(id).then((s) => {
      setSol(s);
      const cd = s.clienteDatos || {};
      const [apellido, ...resto] = (cd.apellido_nombre || s.clienteNombre || "").split(",");
      setForm({
        apellido: (apellido || "").trim(), nombres: resto.join(",").trim(),
        dni: cd.dni || "", cuil: cd.cuil || "",
        email: cd.email || s.datosAdicionales?.portal_email || "", telefono: cd.telefono || "",
        domicilio: cd.domicilio || "", localidad: cd.localidad || "", copiar_documentos: true,
      });
    }).catch((e) => setError(e.message));
    creditos.ppSolicitudDocs(id).then((d) => setDocs(d.items || [])).catch(() => setDocs([]));
  }, [id]);

  async function crear(e) {
    e.preventDefault();
    const f = form;
    const cuil = f.cuil.replace(/\D/g, ""), dni = f.dni.replace(/\D/g, "");
    if (!f.apellido.trim() || !f.nombres.trim()) { setError("Completá apellido y nombres."); return; }
    if (!dni && !cuil) { setError("Hace falta el DNI o el CUIL."); return; }
    if (cuil && cuil.length !== 11) { setError("El CUIL debe tener 11 dígitos."); return; }
    setCreando(true); setError("");
    try {
      const r = await creditos.ppSolicitudPromover(id, {
        apellido_nombre: `${f.apellido.trim()}, ${f.nombres.trim()}`, dni, cuil,
        email: f.email.trim(), telefono: f.telefono.trim(), domicilio: f.domicilio.trim(), localidad: f.localidad.trim(),
        copiar_documentos: f.copiar_documentos,
      });
      const texto = (r.yaExistia ? "La persona ya estaba en Clientes: se vinculó a la solicitud."
                                 : "Cliente creado en el módulo Clientes y vinculado a la solicitud.") + resumenDocs(r.documentos);
      setHecho({ texto, clienteId: r.clienteId });
      setSol(r.solicitud);
      avisar({ tipo: "cliente-vinculado", solicitud: r.solicitud, texto, clienteId: r.clienteId });
    } catch (e) { setError(e.message); }
    finally { setCreando(false); }
  }

  const yaVinculada = sol && sol.solicitanteTipo !== "NO_REGISTRADO";

  return (
    <div className="max-w-2xl">
      <PageHeader
        titulo="Crear cliente con los datos de la solicitud"
        descripcion={sol ? `${sol.numero} · alta en el módulo Clientes` : "Alta en el módulo Clientes"}
      />

      {error && <div className="mb-4"><Alerta>{error}</Alerta></div>}
      {hecho && (
        <div className="mb-4">
          <Alerta tipo="ok">
            {hecho.texto}{" "}
            {hecho.clienteId && <Link to={`/modules/clientes/${hecho.clienteId}`} className="underline font-medium">Ver ficha del cliente</Link>}
            {" "}Ya podés cerrar esta solapa: la solicitud se actualizó.
          </Alerta>
        </div>
      )}
      {!hecho && yaVinculada && (
        <div className="mb-4"><Alerta tipo="warn">La solicitud ya tiene un cliente del padrón vinculado.</Alerta></div>
      )}

      {form && !hecho && !yaVinculada && (
        <Card>
          <form onSubmit={crear}>
            <p className="text-sm text-gray-500 mb-3">
              Revisá lo que declaró el solicitante y completá lo que falte (la web no trae el CUIL). Si la persona ya
              existe en Clientes (mismo documento), no se duplica: se vincula.
            </p>
            <div className="grid sm:grid-cols-2 gap-3">
              {CAMPOS.map(([k, l]) => (
                <Field key={k} label={l}>
                  <input className="input" value={form[k]} inputMode={["dni", "cuil", "telefono"].includes(k) ? "numeric" : undefined}
                         onChange={(e) => setForm((f) => ({ ...f, [k]: e.target.value }))} />
                </Field>
              ))}
            </div>
            {docs.length > 0 && (
              <label className="flex items-center gap-2 mt-4 text-sm text-gray-600">
                <input type="checkbox" checked={form.copiar_documentos}
                       onChange={(e) => setForm((f) => ({ ...f, copiar_documentos: e.target.checked }))} />
                Guardar los {docs.length} documento(s) adjuntos en la ficha del cliente
              </label>
            )}
            <div className="flex justify-end gap-2 mt-5">
              <Boton variante="secundario" type="button" onClick={() => window.close()}>Cancelar</Boton>
              <Boton type="submit" disabled={creando}>{creando ? "Creando…" : "Crear cliente"}</Boton>
            </div>
          </form>
        </Card>
      )}
    </div>
  );
}
