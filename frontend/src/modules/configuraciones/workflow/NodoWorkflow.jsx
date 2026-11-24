import { memo } from "react";
import { Handle, Position } from "@xyflow/react";
import { Bell, CheckCircle2, CircleStop, GitFork, Play, UserCheck } from "lucide-react";
import { ETIQUETA_TIPO, RESULTADOS, ROLES, nombreDe } from "./grafo";

/** Estilo por tipo de nodo: sólo clases del tema (cambian con claro/oscuro). */
export const ESTILO_TIPO = {
  inicio: { icono: Play, borde: "border-green-500", fondo: "bg-green-50", texto: "text-green-700", forma: "rounded-full" },
  aprobacion: { icono: UserCheck, borde: "border-blue-500", fondo: "bg-blue-50", texto: "text-blue-700", forma: "rounded-xl" },
  decision: { icono: GitFork, borde: "border-amber-500", fondo: "bg-amber-50", texto: "text-amber-700", forma: "rounded-xl" },
  notificacion: { icono: Bell, borde: "border-yellow-500", fondo: "bg-yellow-50", texto: "text-yellow-700", forma: "rounded-xl" },
  fin: { icono: CircleStop, borde: "border-red-500", fondo: "bg-red-50", texto: "text-red-700", forma: "rounded-full" },
};

/** Una línea que dice quién actúa en el nodo. */
export function resumenNodo(n) {
  if (n.tipo === "aprobacion") {
    const a = n.asignar || {};
    const quien = a.tipo === "grupo" ? `grupo ${a.valor || "—"}` : a.tipo === "rol" ? (ROLES[a.valor] || a.valor) : "sin asignar";
    return `${quien}${n.cuatroOjos === false ? "" : " · cuatro-ojos"}`;
  }
  if (n.tipo === "fin") return RESULTADOS[n.resultado] || "sin resultado";
  if (n.tipo === "notificacion") return `${(n.destinatarios || []).length} destinatario(s)`;
  if (n.tipo === "decision") return "elige el camino";
  return "";
}

const MARCA = { agregado: "ring-4 ring-green-300", modificado: "ring-4 ring-amber-300" };

function NodoWorkflow({ data, selected }) {
  const n = data.nodo;
  const est = ESTILO_TIPO[n.tipo] || ESTILO_TIPO.aprobacion;
  const Icono = est.icono;
  const errores = data.problemas.filter((x) => x.nivel === "error");
  const avisos = data.problemas.filter((x) => x.nivel === "aviso");
  const borde = errores.length ? "border-red-500" : avisos.length ? "border-amber-400" : est.borde;
  return (
    <div data-testid={`nodo-${n.id}`}
         className={`relative min-w-[180px] max-w-[240px] border-2 ${borde} ${est.fondo} ${est.forma} px-3 py-2 shadow-sm
                     ${selected ? "ring-2 ring-blue-500" : ""} ${data.marca ? MARCA[data.marca] : ""}`}
         title={[...errores, ...avisos].map((x) => x.mensaje).join("\n") || undefined}>
      {n.tipo !== "inicio" && <Handle type="target" id="arriba" position={Position.Top} className="!w-3 !h-3 !bg-gray-400" />}
      {/* Lateral derecho: por ahí sale el «rechazado» y entran las vueltas atrás, así no cruzan los nodos. */}
      <Handle type="target" id="der-entrada" position={Position.Right} className="!w-2 !h-2 !bg-gray-300 !top-[70%]" />
      <div className="flex items-center gap-2">
        <Icono size={16} className={`${est.texto} shrink-0`} aria-hidden />
        <div className="min-w-0">
          <p className={`text-[10px] uppercase tracking-wide font-semibold ${est.texto}`}>{ETIQUETA_TIPO[n.tipo]}</p>
          <p className="text-sm font-semibold text-gray-800 truncate">{nombreDe(n)}</p>
          {resumenNodo(n) && <p className="text-xs text-gray-500 truncate">{resumenNodo(n)}</p>}
        </div>
      </div>
      {(errores.length > 0 || avisos.length > 0) && (
        <span className={`absolute -top-2 -right-2 text-[10px] font-bold rounded-full px-1.5 py-0.5 text-white
                          ${errores.length ? "bg-red-600" : "bg-amber-500"}`}>
          {errores.length || avisos.length}
        </span>
      )}
      {data.marca && <CheckCircle2 size={14} className="absolute -top-2 -left-2 text-green-600 bg-surface rounded-full" aria-label={data.marca} />}
      {n.tipo !== "fin" && <Handle type="source" id="abajo" position={Position.Bottom} className="!w-3 !h-3 !bg-gray-500" />}
      {n.tipo === "aprobacion" && (
        <Handle type="source" id="der" position={Position.Right} className="!w-3 !h-3 !bg-red-500 !top-[35%]" title="Si rechaza" />
      )}
    </div>
  );
}

export default memo(NodoWorkflow);
