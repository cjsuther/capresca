import { useCallback, useMemo, useRef, useState } from "react";
import { Background, Controls, MiniMap, Panel, ReactFlow } from "@xyflow/react";
import "@xyflow/react/dist/base.css";
import { Download, LayoutGrid } from "lucide-react";
import NodoWorkflow, { ESTILO_TIPO } from "./NodoWorkflow";
import PanelPropiedades from "./PanelPropiedades";
import {
  ETIQUETA_TIPO, actualizarConexion, actualizarNodo, agregarNodo, conectar, crearNodo, nombreDe, problemasPorElemento,
  quitarConexion, quitarNodo,
} from "./grafo";
import { aAristasFlow, aNodosFlow, leerCambiosAristas, leerCambiosNodos, posicionNueva } from "./flow";
import { ordenar } from "./layout";
import { exportarPng, nombreArchivo } from "./exportar";

const TIPOS_NODO = { workflow: NodoWorkflow };

// React Flow trae sus colores (y sigue el tema del sistema operativo); acá se atan a los tokens del
// tema de Portezuelo, que cambian con la clase `dark` del documento.
const VARIABLES_TEMA = {
  "--xy-background-color": "rgb(var(--c-gray-50))",
  "--xy-background-pattern-dots-color": "rgb(var(--c-gray-300))",
  "--xy-minimap-background-color": "rgb(var(--c-surface))",
  "--xy-edge-label-background-color": "rgb(var(--c-surface))",
  "--xy-controls-button-background-color": "rgb(var(--c-surface))",
  "--xy-controls-button-color": "rgb(var(--c-gray-700))",
  "--xy-controls-button-border-color": "rgb(var(--c-gray-200))",
};
const esquemaColor = () => (typeof document !== "undefined" && document.documentElement.classList.contains("dark") ? "dark" : "light");
const PALETA = ["aprobacion", "decision", "notificacion", "fin"];   // el Inicio es único y ya está

/**
 * Lienzo del workflow: paleta, diagrama (React Flow) y panel de propiedades.
 * Controlado: recibe {grafo, layout} y avisa cada cambio con onCambio(grafo, layout).
 */
export default function EditorWorkflow({ proceso, version, grafo, layout, problemas = [], variables = {}, personas,
                                         soloLectura = false, marcas = {}, onCambio, onError }) {
  const [seleccion, setSeleccion] = useState(null);
  const [medidas, setMedidas] = useState({});
  const [aviso, setAviso] = useState("");
  const [ordenando, setOrdenando] = useState(false);
  const contenedor = useRef(null);
  const instancia = useRef(null);

  const porElemento = useMemo(() => problemasPorElemento(problemas), [problemas]);
  const nodos = useMemo(() => aNodosFlow(grafo, layout, { problemas: porElemento.nodos, seleccion, medidas, marcas, soloLectura }),
    [grafo, layout, porElemento, seleccion, medidas, marcas, soloLectura]);
  const aristas = useMemo(() => aAristasFlow(grafo, { variables, problemas: porElemento.conexiones, seleccion, soloLectura, posiciones: layout }),
    [grafo, variables, porElemento, seleccion, soloLectura, layout]);

  const quitar = useCallback((sel) => {
    if (soloLectura || !sel) return;
    if (sel.tipo === "nodo") {
      const n = grafo.nodos.find((x) => x.id === sel.id);
      if (!n || n.tipo === "inicio") return;
      const { [sel.id]: _, ...resto } = layout;
      onCambio(quitarNodo(grafo, sel.id), resto);
    } else {
      onCambio(quitarConexion(grafo, sel.id), layout);
    }
    setSeleccion(null);
  }, [grafo, layout, onCambio, soloLectura]);

  const onNodesChange = useCallback((cambios) => {
    const r = leerCambiosNodos(cambios, { layout, medidas, seleccion });
    if (r.medidas !== medidas) setMedidas(r.medidas);
    if (r.seleccion !== seleccion) setSeleccion(r.seleccion);
    if (soloLectura) return;
    let g = grafo;
    for (const id of r.quitar) if (g.nodos.find((x) => x.id === id)?.tipo !== "inicio") g = quitarNodo(g, id);
    if (g !== grafo || r.layout !== layout) onCambio(g, r.layout);
  }, [grafo, layout, medidas, seleccion, soloLectura, onCambio]);

  const onEdgesChange = useCallback((cambios) => {
    const r = leerCambiosAristas(cambios, { seleccion });
    if (r.seleccion !== seleccion) setSeleccion(r.seleccion);
    if (soloLectura || !r.quitar.length) return;
    onCambio(r.quitar.reduce((g, id) => quitarConexion(g, id), grafo), layout);
  }, [grafo, layout, seleccion, soloLectura, onCambio]);

  const onConnect = useCallback(({ source, target, sourceHandle }) => {
    if (soloLectura) return;
    const { grafo: g, error } = conectar(grafo, source, target, sourceHandle === "der" ? "rechazado" : null);
    setAviso(error || "");
    if (!error) onCambio(g, layout);
  }, [grafo, layout, soloLectura, onCambio]);

  const agregar = (tipo) => {
    const n = crearNodo(grafo, tipo);
    const sel = seleccion?.tipo === "nodo" ? seleccion.id : null;
    onCambio(agregarNodo(grafo, n), { ...layout, [n.id]: posicionNueva(layout, sel) });
    setSeleccion({ tipo: "nodo", id: n.id });
  };

  const autoOrdenar = async () => {
    setOrdenando(true);
    try {
      const nuevo = await ordenar(grafo, medidas);
      onCambio(grafo, nuevo);
      setTimeout(() => instancia.current?.fitView?.({ padding: 0.2 }), 60);   // después de que se dibujen las posiciones nuevas
    } catch (e) {
      onError?.(`No se pudo ordenar el diagrama: ${e.message}`);
    } finally {
      setOrdenando(false);
    }
  };

  const exportar = async () => {
    try {
      await exportarPng(contenedor.current, nodos, nombreArchivo(proceso, version));
    } catch (e) {
      onError?.(`No se pudo exportar: ${e.message}`);
    }
  };

  const errores = problemas.filter((x) => x.nivel === "error");
  const avisos = problemas.filter((x) => x.nivel === "aviso");

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-3">
      <div className="border border-gray-200 rounded-xl overflow-hidden bg-surface">
        {!soloLectura && (
          <div className="flex flex-wrap items-center gap-2 px-3 py-2 border-b border-gray-200" role="toolbar" aria-label="Agregar nodo">
            <span className="text-xs text-gray-500">Agregar:</span>
            {PALETA.map((tipo) => {
              const Icono = ESTILO_TIPO[tipo].icono;
              return (
                <button key={tipo} type="button" onClick={() => agregar(tipo)}
                        className={`inline-flex items-center gap-1 text-sm px-2 py-1 rounded-lg border ${ESTILO_TIPO[tipo].borde} ${ESTILO_TIPO[tipo].fondo} ${ESTILO_TIPO[tipo].texto}`}>
                  <Icono size={14} aria-hidden /> {ETIQUETA_TIPO[tipo]}
                </button>
              );
            })}
            <span className="text-xs text-gray-400">Conectá arrastrando desde el punto de abajo de un nodo al de arriba de otro. Supr borra.</span>
          </div>
        )}
        {aviso && <p role="status" className="text-sm text-amber-700 px-3 py-1 border-b border-gray-200">{aviso}</p>}
        <div ref={contenedor} className="h-[560px] bg-gray-50" data-testid="lienzo" style={{ ...VARIABLES_TEMA, colorScheme: esquemaColor() }}>
          <ReactFlow nodes={nodos} edges={aristas} nodeTypes={TIPOS_NODO}
                     onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onConnect={onConnect}
                     onInit={(i) => { instancia.current = i; }}
                     onPaneClick={() => setSeleccion(null)}
                     nodesDraggable={!soloLectura} nodesConnectable={!soloLectura} elementsSelectable
                     deleteKeyCode={soloLectura ? null : ["Delete", "Backspace"]}
                     fitView fitViewOptions={{ padding: 0.2 }} minZoom={0.2} proOptions={{ hideAttribution: true }}>
            <Background gap={18} />
            <Controls showInteractive={false} />
            <MiniMap pannable zoomable />
            <Panel position="top-right" className="flex gap-1">
              {!soloLectura && (
                <button type="button" onClick={autoOrdenar} disabled={ordenando}
                        className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-lg border border-gray-300 bg-surface text-gray-700 disabled:opacity-50">
                  <LayoutGrid size={14} /> {ordenando ? "Ordenando…" : "Ordenar"}
                </button>
              )}
              <button type="button" onClick={exportar}
                      className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-lg border border-gray-300 bg-surface text-gray-700">
                <Download size={14} /> PNG
              </button>
            </Panel>
          </ReactFlow>
        </div>
      </div>

      <aside className="grid gap-3 content-start">
        <section className="border border-gray-200 rounded-xl bg-surface p-3" aria-label="Validación">
          <h3 className="text-xs uppercase tracking-wide font-semibold text-gray-500 mb-2">Validación</h3>
          {errores.length === 0 && avisos.length === 0 && <p className="text-sm text-green-700">✔ Sin problemas</p>}
          <ul className="grid gap-1 text-sm">
            {[...errores, ...avisos].map((x, i) => (
              <li key={i}>
                <button type="button" className={`text-left hover:underline ${x.nivel === "error" ? "text-red-600" : "text-amber-700"}`}
                        onClick={() => setSeleccion(x.conexion ? { tipo: "conexion", id: x.conexion } : x.nodo ? { tipo: "nodo", id: x.nodo } : null)}>
                  {x.nivel === "error" ? "✖" : "⚠"} {x.mensaje}
                </button>
              </li>
            ))}
          </ul>
        </section>
        <section className="border border-gray-200 rounded-xl bg-surface p-3" aria-label="Propiedades">
          <h3 className="text-xs uppercase tracking-wide font-semibold text-gray-500 mb-2">
            Propiedades{seleccion?.tipo === "nodo" ? ` · ${nombreDe(grafo.nodos.find((n) => n.id === seleccion.id))}` : ""}
          </h3>
          <PanelPropiedades grafo={grafo} seleccion={seleccion} variables={variables} personas={personas}
                            soloLectura={soloLectura} problemas={porElemento.nodos}
                            onCambiarNodo={(id, c) => onCambio(actualizarNodo(grafo, id, c), layout)}
                            onCambiarConexion={(id, c) => onCambio(actualizarConexion(grafo, id, c), layout)}
                            onQuitar={quitar} />
        </section>
      </aside>
    </div>
  );
}
