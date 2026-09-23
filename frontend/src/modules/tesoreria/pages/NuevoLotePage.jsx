import { useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowLeft, Plus, Trash2, Upload } from "lucide-react";
import { crearLote, mensajeDeError } from "../../../api/tesoreria";
import { Alerta, Boton, Card, Field, PageHeader } from "../../../components/ui";
import { leerCsv, montoDesdeTexto, problemaDeFila } from "../csv";
import { money } from "../estados";

const leerArchivo = (f) => new Promise((ok, mal) => {
  const r = new FileReader();
  r.onload = () => ok(String(r.result || ""));
  r.onerror = () => mal(r.error);
  r.readAsText(f);
});

const VACIA = { beneficiario: "", documento: "", cbu: "", monto: "", concepto: "" };

export default function NuevoLotePage() {
  const navigate = useNavigate();
  const archivo = useRef(null);
  const [descripcion, setDescripcion] = useState("");
  const [filas, setFilas] = useState([{ ...VACIA }]);
  const [error, setError] = useState("");
  const [aviso, setAviso] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [intentado, setIntentado] = useState(false);

  const cambiar = (i, campo, valor) => setFilas((fs) => fs.map((f, j) => (j === i ? { ...f, [campo]: valor } : f)));
  const usadas = filas.filter((f) => Object.values(f).some((v) => String(v).trim()));
  const problemas = usadas.map(problemaDeFila);
  const validas = problemas.filter((p) => !p).length;
  const total = usadas.reduce((s, f) => s + (montoDesdeTexto(f.monto) > 0 ? montoDesdeTexto(f.monto) : 0), 0);

  const importar = async (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    const nuevas = leerCsv(await leerArchivo(f));
    e.target.value = "";
    if (!nuevas.length) { setError("El archivo no tiene filas."); return; }
    setFilas((fs) => [...fs.filter((x) => Object.values(x).some((v) => String(v).trim())), ...nuevas]);
    setAviso(`Se importaron ${nuevas.length} fila(s) de ${f.name}. Revisalas antes de crear el lote.`);
    setError("");
  };

  const guardar = async (e) => {
    e.preventDefault();
    setIntentado(true);
    setError("");
    if (!descripcion.trim()) { setError("Indicá una descripción del lote."); return; }
    if (!usadas.length) { setError("Cargá al menos un pago."); return; }
    if (problemas.some(Boolean)) { setError("Hay filas con datos inválidos (marcadas en rojo)."); return; }
    setGuardando(true);
    try {
      const r = await crearLote({
        descripcion: descripcion.trim(),
        pagos: usadas.map((f) => ({ beneficiario: f.beneficiario.trim(), documento: f.documento.trim(),
                                   cbu: f.cbu.replace(/\D/g, ""), monto: montoDesdeTexto(f.monto), concepto: f.concepto.trim() })),
      });
      navigate(`/modules/tesoreria/lotes/${r.id}`);
    } catch (err) {
      setError(mensajeDeError(err, "No se pudo crear el lote"));
      setGuardando(false);
    }
  };

  return (
    <form onSubmit={guardar} className="space-y-4">
      <Link to="/modules/tesoreria/lotes" className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700">
        <ArrowLeft size={14} /> Lotes de pagos
      </Link>
      <PageHeader titulo="Nuevo lote manual"
                  descripcion="Cargá los pagos a mano o importalos de un CSV (beneficiario; documento; cbu; monto; concepto). El lote queda pendiente de aprobación.">
        <input ref={archivo} type="file" accept=".csv,text/csv,text/plain" className="hidden" onChange={importar}
               data-testid="archivo-csv" />
        <Boton type="button" variante="secundario" onClick={() => archivo.current?.click()} className="flex items-center gap-2">
          <Upload size={15} /> Importar CSV
        </Boton>
      </PageHeader>

      <Alerta>{error}</Alerta>
      {aviso && <Alerta tipo="ok">{aviso}</Alerta>}

      <Card>
        <Field label="Descripción del lote">
          <input className="input w-full" value={descripcion} onChange={(e) => setDescripcion(e.target.value)}
                 placeholder="Ej.: Pago a proveedores septiembre" maxLength={200} />
        </Field>
      </Card>

      <Card padding={false}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[860px]">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50 text-left text-xs text-gray-500">
                <th className="px-3 py-2 font-medium">Beneficiario</th>
                <th className="px-3 py-2 font-medium">CUIT / DNI</th>
                <th className="px-3 py-2 font-medium">CBU</th>
                <th className="px-3 py-2 font-medium text-right">Monto</th>
                <th className="px-3 py-2 font-medium">Concepto</th>
                <th className="px-3 py-2" />
              </tr>
            </thead>
            <tbody>
              {filas.map((f, i) => {
                const usada = Object.values(f).some((v) => String(v).trim());
                const problema = usada && intentado ? problemaDeFila(f) : "";
                return (
                  <tr key={i} className={`border-b border-gray-100 ${problema ? "bg-red-50" : ""}`}>
                    <td className="px-3 py-1.5"><input aria-label={`Beneficiario ${i + 1}`} className="input w-full" value={f.beneficiario} onChange={(e) => cambiar(i, "beneficiario", e.target.value)} /></td>
                    <td className="px-3 py-1.5"><input aria-label={`Documento ${i + 1}`} className="input w-32" value={f.documento} onChange={(e) => cambiar(i, "documento", e.target.value)} /></td>
                    <td className="px-3 py-1.5"><input aria-label={`CBU ${i + 1}`} className="input w-56 tabular-nums" inputMode="numeric" value={f.cbu} onChange={(e) => cambiar(i, "cbu", e.target.value)} /></td>
                    <td className="px-3 py-1.5"><input aria-label={`Monto ${i + 1}`} className="input w-32 text-right tabular-nums" inputMode="decimal" value={f.monto} onChange={(e) => cambiar(i, "monto", e.target.value)} /></td>
                    <td className="px-3 py-1.5">
                      <input aria-label={`Concepto ${i + 1}`} className="input w-full" value={f.concepto} onChange={(e) => cambiar(i, "concepto", e.target.value)} />
                      {problema && <p className="text-xs text-red-600 mt-0.5">{problema}</p>}
                    </td>
                    <td className="px-3 py-1.5 text-right">
                      <button type="button" aria-label={`Quitar fila ${i + 1}`} className="p-1.5 text-gray-400 hover:text-red-600 rounded-lg"
                              onClick={() => setFilas((fs) => (fs.length > 1 ? fs.filter((_, j) => j !== i) : [{ ...VACIA }]))}>
                        <Trash2 size={15} />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <div className="flex flex-wrap items-center gap-3 px-4 py-3 border-t border-gray-200">
          <Boton type="button" variante="secundario" onClick={() => setFilas((fs) => [...fs, { ...VACIA }])} className="flex items-center gap-1">
            <Plus size={15} /> Agregar pago
          </Boton>
          <span className="text-sm text-gray-500 ml-auto tabular-nums">
            {validas} pago(s) válidos · Total {money(total)}
          </span>
          <Boton type="submit" disabled={guardando}>{guardando ? "Creando…" : "Crear lote"}</Boton>
        </div>
      </Card>
    </form>
  );
}
