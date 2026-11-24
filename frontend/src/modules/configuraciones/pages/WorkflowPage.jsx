import { lazy, Suspense, useState } from "react";
import { PageHeader, Card } from "../../../components/ui";
import WorkflowListaPage from "./WorkflowListaPage";

// El editor (React Flow) se carga recién al abrir la pestaña: no pesa en el resto del frontend.
const WorkflowEditorPage = lazy(() => import("../workflow/WorkflowEditorPage"));

const PESTANAS = [["diagrama", "Diagrama"], ["lista", "Vista lista"]];

/** Workflow de aprobaciones: editor gráfico (Diagrama) y la vista lista de sólo lectura. */
export default function WorkflowPage() {
  const [pestana, setPestana] = useState("diagrama");
  return (
    <>
      <PageHeader titulo="Workflow de aprobaciones"
                  descripcion="Qué operaciones exigen aprobación y quién aprueba cada paso, dibujado como un diagrama. Los cambios se arman en un borrador y rigen recién cuando se publican." />
      <div role="tablist" aria-label="Vistas del workflow" className="flex gap-1 mb-4 border-b border-gray-200">
        {PESTANAS.map(([clave, texto]) => (
          <button key={clave} role="tab" type="button" aria-selected={pestana === clave} onClick={() => setPestana(clave)}
                  className={`px-4 py-2 text-sm -mb-px border-b-2 ${pestana === clave
                    ? "border-blue-600 text-blue-700 font-medium" : "border-transparent text-gray-500 hover:text-gray-700"}`}>
            {texto}
          </button>
        ))}
      </div>
      {pestana === "diagrama" ? (
        <Suspense fallback={<Card>Cargando el editor…</Card>}><WorkflowEditorPage /></Suspense>
      ) : (
        <WorkflowListaPage embebida />
      )}
    </>
  );
}
