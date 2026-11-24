import { useEffect, useMemo, useState } from "react";
import { PageHeader, Card, Alerta } from "../../../components/ui";
import { Pill } from "../../../components/ui/Pill";
import { listarWorkflow, mensajeDeError } from "../../../api/configuraciones";

const MODULOS = { creditos: "Créditos", tesoreria: "Tesorería" };
const ROLES = {
  APROBAR: "Aprobador (permiso aprobaciones:aprobar)",
  SUPERVISAR: "Supervisor (permiso aprobaciones:supervisar)",
};

/**
 * Vista lista del workflow de aprobaciones: las reglas en serie tal como las ejecutan hoy Créditos y
 * Tesorería. Es de SÓLO LECTURA: el workflow se edita en el editor gráfico, que publica versiones y
 * las refleja acá (docs/decisiones-workflows.md).
 */
export default function WorkflowPage() {
  const [data, setData] = useState({ reglas: [] });
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    listarWorkflow()
      .then((d) => { setData(d); setError(""); })
      .catch((e) => setError(mensajeDeError(e, "No se pudo cargar el workflow")))
      .finally(() => setCargando(false));
  }, []);

  const porModulo = useMemo(() => {
    const g = {};
    data.reglas.forEach((r) => { (g[r.modulo] ||= []).push(r); });
    return Object.entries(g);
  }, [data.reglas]);

  return (
    <>
      <PageHeader titulo="Workflow de aprobaciones"
                  descripcion="Qué operaciones exigen aprobación, en cuántos niveles y quién aprueba cada uno, tal como lo aplican hoy los módulos. Cuatro-ojos impide aprobar algo en lo que ya se intervino." />

      {error && <div className="mb-4"><Alerta>{error}</Alerta></div>}
      {!cargando && !error && (
        <div className="mb-4">
          <Alerta tipo="warn">Vista de sólo lectura. Los cambios se hacen en el editor gráfico: se arma un borrador y, al publicarlo, se refleja acá.</Alerta>
        </div>
      )}
      {cargando && <Card>Cargando…</Card>}

      {porModulo.map(([modulo, reglas]) => (
        <section key={modulo} className="mb-6">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500 mb-2">{MODULOS[modulo] || modulo}</h2>
          <div className="grid gap-4">
            {reglas.map((r) => (
              <Card key={r.id} padding={false}>
                <div className="flex flex-wrap items-start gap-3 px-4 py-3 border-b border-gray-200">
                  <div className="min-w-0">
                    <h3 className="font-semibold text-gray-800">{r.nombre}</h3>
                    <p className="text-sm text-gray-500">{r.descripcion}</p>
                  </div>
                  <span className="flex-1" />
                  {r.versionPublicada && <Pill tono="neutral">Versión {r.versionPublicada}</Pill>}
                  <Pill tono={r.activo ? "ok" : "neutral"}>{r.activo ? "Activa" : "Inactiva"}</Pill>
                </div>

                <ol aria-label={`Niveles de ${r.nombre}`} className="divide-y divide-gray-100">
                  {r.niveles.map((n) => (
                    <li key={n.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
                      <span className="w-7 h-7 rounded-full bg-blue-50 text-blue-700 text-sm font-semibold flex items-center justify-center shrink-0">
                        {n.orden}
                      </span>
                      <div className="min-w-0">
                        <p className="font-medium text-gray-800">{n.nombre}</p>
                        <p className="text-xs text-gray-500">
                          {ROLES[n.rol] || n.rol}{n.cuatroOjos ? " · cuatro-ojos" : " · sin cuatro-ojos"}
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {n.usuarios.map((u) => (
                          <span key={u.id} className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full ${
                            u.modo === "INCLUIR" ? "bg-green-100 text-green-700" : "bg-red-100 text-red-600"}`}>
                            {u.modo === "INCLUIR" ? "+" : "−"} {u.username}
                          </span>
                        ))}
                      </div>
                    </li>
                  ))}
                </ol>
              </Card>
            ))}
          </div>
        </section>
      ))}
    </>
  );
}
