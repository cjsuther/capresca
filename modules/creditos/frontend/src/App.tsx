import { useEffect } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { getToken, irAlLogin } from "./api";
import { PermisosProvider, usePermisos, rutaMenuDe } from "./permisos";
import Sidebar from "./components/Sidebar";
import Topbar, { initTheme } from "./components/Topbar";

initTheme();
// Créditos
import Solicitudes from "./pages/Solicitudes";
import Simulador from "./pages/Simulador";
import SituacionCliente from "./pages/creditos/SituacionCliente";
import EstadisticasCartera from "./pages/creditos/EstadisticasCartera";
import PorCartera from "./pages/creditos/PorCartera";
import TurnosOtorgados from "./pages/creditos/TurnosOtorgados";
import ListadoCreditos from "./pages/creditos/ListadoCreditos";
import InformeCreditos from "./pages/creditos/InformeCreditos";
import CuotasMora from "./pages/creditos/CuotasMora";
import SinDebito from "./pages/creditos/SinDebito";
import PagosEnCaja from "./pages/creditos/PagosEnCaja";
import ResumenCobros from "./pages/creditos/ResumenCobros";
import CuentaCorriente from "./pages/creditos/CuentaCorriente";
import CancelacionCredito from "./pages/creditos/CancelacionCredito";
import BajaCredito from "./pages/creditos/BajaCredito";
import RecalculoCredito from "./pages/creditos/RecalculoCredito";
import TurnosAdmin from "./pages/creditos/TurnosAdmin";
import PendientesCobro from "./pages/creditos/PendientesCobro";
import EnviosPadron from "./pages/creditos/EnviosPadron";
import Jubilados from "./pages/creditos/Jubilados";
import ConfigurarCreditos from "./pages/creditos/ConfigurarCreditos";
import LiquidacionLote from "./pages/creditos/LiquidacionLote";
import SistemaCalculos from "./pages/creditos/SistemaCalculos";
import SolicitudesCredito from "./pages/creditos/SolicitudesCredito";
import ParametrosCreditos from "./pages/creditos/ParametrosCreditos";
import CajaCreditos from "./pages/creditos/CajaCreditos";
import SituacionClientePP from "./pages/creditos/SituacionClientePP";
import TableroCartera from "./pages/creditos/TableroCartera";
import InboxAprobaciones from "./pages/creditos/InboxAprobaciones";
import ControlesVersion from "./pages/ControlesVersion";
import PrincipiosArquitectura from "./pages/PrincipiosArquitectura";
import PrincipiosDiseno from "./pages/PrincipiosDiseno";
import Procesos from "./pages/Procesos";
import LineasCredito from "./pages/LineasCredito";
// Caja
import Cobranza from "./pages/caja/Cobranza";
import ControlCaja from "./pages/caja/ControlCaja";
import AplicativoQuiniela from "./pages/caja/AplicativoQuiniela";
import DeudaAgencia from "./pages/caja/DeudaAgencia";
import CobranzasPeriodo from "./pages/caja/CobranzasPeriodo";
import IngresosBrutos from "./pages/caja/IngresosBrutos";
import RecaudacionAnual from "./pages/caja/RecaudacionAnual";
import LiquidacionesCobradas from "./pages/caja/LiquidacionesCobradas";
import InteresesIva from "./pages/caja/InteresesIva";
import PlanillaContable from "./pages/caja/PlanillaContable";
import PagosRealizados from "./pages/caja/PagosRealizados";
import PremiosQuiniela from "./pages/caja/PremiosQuiniela";
import ChequesAgencias from "./pages/caja/ChequesAgencias";
import PremiosCompensados from "./pages/caja/PremiosCompensados";
import ReimpresionRecibos from "./pages/caja/ReimpresionRecibos";
// Tesorería
import OrdenesPago from "./pages/tesoreria/OrdenesPago";
import AutorizacionesOP from "./pages/tesoreria/AutorizacionesOP";
import ReporteOP from "./pages/tesoreria/ReporteOP";
import InformeOP from "./pages/tesoreria/InformeOP";
import Chequeras from "./pages/tesoreria/Chequeras";
import ChequesEmitidos from "./pages/tesoreria/ChequesEmitidos";
import BuscaEgresos from "./pages/tesoreria/BuscaEgresos";
// Contabilidad
import LibroDiario from "./pages/contabilidad/LibroDiario";
import BalanceMayor from "./pages/contabilidad/BalanceMayor";
import Impuestos from "./pages/contabilidad/Impuestos";
import PlanCuentas from "./pages/contabilidad/PlanCuentas";
import Asientos from "./pages/contabilidad/Asientos";
import EstadosContables from "./pages/contabilidad/EstadosContables";
import Imputaciones from "./pages/contabilidad/Imputaciones";
import Ejercicios from "./pages/contabilidad/Ejercicios";
import Conciliacion from "./pages/contabilidad/Conciliacion";
import Centros from "./pages/contabilidad/Centros";
import Indices from "./pages/contabilidad/Indices";
import Feriados from "./pages/contabilidad/Feriados";
import IvaCuotas from "./pages/contabilidad/IvaCuotas";
import IvaPeriodo from "./pages/contabilidad/IvaPeriodo";
import Cierre from "./pages/contabilidad/Cierre";
import Balance from "./pages/contabilidad/Balance";
import CtaCteContable from "./pages/contabilidad/CtaCteContable";
import ContabilidadGeneral from "./pages/contabilidad/ContabilidadGeneral";
import AgenciaHistorico from "./pages/caja/AgenciaHistorico";
// Seguros
import Polizas from "./pages/seguros/Polizas";
import Regimenes from "./pages/seguros/Regimenes";
import InformesSeguros from "./pages/seguros/Informes";
import SeguroAdicional from "./pages/seguros/SeguroAdicional";
import Titulares from "./pages/seguros/Titulares";
// Despacho
import Resoluciones from "./pages/despacho/Resoluciones";
import ModelosResolucion from "./pages/despacho/Modelos";
import Anexos from "./pages/despacho/Anexos";
import Expedientes from "./pages/despacho/Expedientes";
// Otros
import Juegos from "./pages/Juegos";
import IngresosPorJuego from "./pages/juegos/IngresosPorJuego";
import MaestroJuegos from "./pages/juegos/MaestroJuegos";
import ControlSorteos from "./pages/juegos/ControlSorteos";
import FondoGarantia from "./pages/juegos/FondoGarantia";
import Mesa from "./pages/Mesa";
import Tramites from "./pages/mesa/Tramites";
import TramitesIngresados from "./pages/mesa/TramitesIngresados";
// Clientes
import Clientes from "./pages/Clientes";
import Vision360 from "./pages/clientes/Vision360";
import Organismos from "./pages/general/Organismos";
import Oficinas from "./pages/general/Oficinas";
import Proveedores from "./pages/general/Proveedores";
import Companias from "./pages/general/Companias";
import Parametros from "./pages/general/Parametros";
import Auditoria from "./pages/general/Auditoria";
import AuditoriaCambios from "./pages/seguridad/AuditoriaCambios";
import Migradores from "./pages/seguridad/Migradores";
import WorkflowAprobaciones from "./pages/seguridad/WorkflowAprobaciones";
import ModeloDatos from "./pages/seguridad/ModeloDatos";
import { Dialogos } from "./ui/dialog";

function Layout({ children }: { children: React.ReactNode }) {
  return (
    <PermisosProvider>
      <div className="app">
        <Sidebar />
        <div className="main">
          <Topbar />
          <main className="page"><RouteGuard>{children}</RouteGuard></main>
        </div>
      </div>
    </PermisosProvider>
  );
}

// Guard central: si el usuario no tiene al menos CONSULTA sobre la pantalla actual, no la muestra.
function RouteGuard({ children }: { children: React.ReactNode }) {
  const { estado, puedeVer } = usePermisos();
  const { pathname } = useLocation();
  const ruta = rutaMenuDe(pathname);
  if (!estado.cargado || !ruta || puedeVer(ruta)) return <>{children}</>;
  return (
    <div className="card" style={{ maxWidth: 520, margin: "40px auto", textAlign: "center", padding: 32 }}>
      <h2 style={{ marginTop: 0 }}>🔒 Sin acceso</h2>
      <p className="muted">Tu usuario no tiene permiso para ver esta pantalla. Pedí acceso a un administrador
        (Seguridad de Portezuelo → permisos del módulo Créditos).</p>
    </div>
  );
}

// Sin sesión de Portezuelo → a su login (con vuelta a la pantalla pedida).
function IrAlLogin() {
  useEffect(() => { irAlLogin(); }, []);
  return null;
}

function Private({ children }: { children: React.ReactNode }) {
  return getToken() ? <Layout>{children}</Layout> : <IrAlLogin />;
}

export default function App() {
  return (
    <>
    <Dialogos />
    <Routes>
      <Route path="/login" element={<IrAlLogin />} />

      {/* Créditos */}
      <Route path="/creditos/solicitudes" element={<Private><Solicitudes /></Private>} />
      <Route path="/creditos/simulador" element={<Private><Simulador /></Private>} />
      <Route path="/creditos/situacion" element={<Private><SituacionCliente /></Private>} />
      <Route path="/creditos/estadisticas" element={<Private><EstadisticasCartera /></Private>} />
      <Route path="/creditos/por-cartera" element={<Private><PorCartera /></Private>} />
      <Route path="/creditos/turnos" element={<Private><TurnosOtorgados /></Private>} />
      <Route path="/creditos/listado" element={<Private><ListadoCreditos /></Private>} />
      <Route path="/creditos/informe" element={<Private><InformeCreditos /></Private>} />
      <Route path="/creditos/mora" element={<Private><CuotasMora /></Private>} />
      <Route path="/creditos/sin-debito" element={<Private><SinDebito /></Private>} />
      <Route path="/creditos/pagos-caja" element={<Private><PagosEnCaja /></Private>} />
      <Route path="/creditos/resumen-cobros" element={<Private><ResumenCobros /></Private>} />
      <Route path="/creditos/cuenta-corriente" element={<Private><CuentaCorriente /></Private>} />
      <Route path="/creditos/cancelacion" element={<Private><CancelacionCredito /></Private>} />
      <Route path="/creditos/baja" element={<Private><BajaCredito /></Private>} />
      <Route path="/creditos/recalculo" element={<Private><RecalculoCredito /></Private>} />
      <Route path="/creditos/turnos-admin" element={<Private><TurnosAdmin /></Private>} />
      <Route path="/creditos/pendientes" element={<Private><PendientesCobro /></Private>} />
      <Route path="/creditos/envios" element={<Private><EnviosPadron /></Private>} />
      <Route path="/creditos/jubilados" element={<Private><Jubilados /></Private>} />
      <Route path="/creditos/lineas" element={<Private><LineasCredito /></Private>} />
      <Route path="/creditos/configurar" element={<Private><ConfigurarCreditos /></Private>} />
      {/* "Originar Crédito (oferta)" retirado: su flujo está unificado en Solicitudes de crédito (H-195). */}
      <Route path="/creditos/originar" element={<Navigate to="/creditos/solicitudes-credito" replace />} />
      <Route path="/creditos/liquidacion-lote" element={<Private><LiquidacionLote /></Private>} />
      <Route path="/creditos/sistema-calculos" element={<Private><SistemaCalculos /></Private>} />
      <Route path="/creditos/solicitudes-credito" element={<Private><SolicitudesCredito /></Private>} />
      <Route path="/creditos/parametros" element={<Private><ParametrosCreditos /></Private>} />
      <Route path="/creditos/caja" element={<Private><CajaCreditos /></Private>} />
      <Route path="/creditos/situacion-linea" element={<Private><SituacionClientePP /></Private>} />
      <Route path="/creditos/inbox-aprobaciones" element={<Private><InboxAprobaciones /></Private>} />
      <Route path="/creditos/tablero-cartera" element={<Private><TableroCartera /></Private>} />
      <Route path="/controles-version" element={<Private><ControlesVersion /></Private>} />
      <Route path="/controles-version/principios" element={<Private><PrincipiosArquitectura /></Private>} />
      <Route path="/controles-version/principios-diseno" element={<Private><PrincipiosDiseno /></Private>} />
      <Route path="/controles-version/procesos" element={<Private><Procesos /></Private>} />

      {/* Caja */}
      <Route path="/caja/quiniela" element={<Private><AplicativoQuiniela /></Private>} />
      <Route path="/caja/cobranza" element={<Private><Cobranza /></Private>} />
      <Route path="/caja/control" element={<Private><ControlCaja /></Private>} />
      <Route path="/caja/deuda-agencia" element={<Private><DeudaAgencia /></Private>} />
      <Route path="/caja/cobranzas-periodo" element={<Private><CobranzasPeriodo /></Private>} />
      <Route path="/caja/ingresos-brutos" element={<Private><IngresosBrutos /></Private>} />
      <Route path="/caja/recaudacion-anual" element={<Private><RecaudacionAnual /></Private>} />
      <Route path="/caja/liquidaciones-cobradas" element={<Private><LiquidacionesCobradas /></Private>} />
      <Route path="/caja/intereses-iva" element={<Private><InteresesIva /></Private>} />
      <Route path="/caja/planilla-contable" element={<Private><PlanillaContable /></Private>} />
      <Route path="/caja/pagos-realizados" element={<Private><PagosRealizados /></Private>} />
      <Route path="/caja/premios" element={<Private><PremiosQuiniela /></Private>} />
      <Route path="/caja/cheques-agencias" element={<Private><ChequesAgencias /></Private>} />
      <Route path="/caja/premios-compensados" element={<Private><PremiosCompensados /></Private>} />
      <Route path="/caja/reimpresion-recibos" element={<Private><ReimpresionRecibos /></Private>} />

      {/* Tesorería */}
      <Route path="/tesoreria/autorizaciones" element={<Private><AutorizacionesOP /></Private>} />
      <Route path="/tesoreria/ordenes" element={<Private><OrdenesPago /></Private>} />
      <Route path="/tesoreria/reporte" element={<Private><ReporteOP /></Private>} />
      <Route path="/tesoreria/informe" element={<Private><InformeOP /></Private>} />
      <Route path="/tesoreria/cheques" element={<Private><ChequesEmitidos /></Private>} />
      <Route path="/tesoreria/egresos" element={<Private><BuscaEgresos /></Private>} />
      <Route path="/tesoreria/chequeras" element={<Private><Chequeras /></Private>} />

      {/* Contabilidad */}
      <Route path="/contabilidad/mayor" element={<Private><BalanceMayor /></Private>} />
      <Route path="/contabilidad/plan-cuentas" element={<Private><PlanCuentas /></Private>} />
      <Route path="/contabilidad/asientos" element={<Private><Asientos /></Private>} />
      <Route path="/contabilidad/estados" element={<Private><EstadosContables /></Private>} />
      <Route path="/contabilidad/imputaciones" element={<Private><Imputaciones /></Private>} />
      <Route path="/contabilidad/ejercicios" element={<Private><Ejercicios /></Private>} />
      <Route path="/contabilidad/conciliacion" element={<Private><Conciliacion /></Private>} />
      <Route path="/contabilidad/centros-costo" element={<Private><Centros /></Private>} />
      <Route path="/contabilidad/impuestos" element={<Private><Impuestos /></Private>} />
      <Route path="/contabilidad/indices" element={<Private><Indices /></Private>} />
      <Route path="/contabilidad/feriados" element={<Private><Feriados /></Private>} />
      <Route path="/contabilidad/iva-cuotas" element={<Private><IvaCuotas /></Private>} />
      <Route path="/contabilidad/libro-diario" element={<Private><LibroDiario /></Private>} />
      <Route path="/contabilidad/balance" element={<Private><Balance /></Private>} />
      <Route path="/contabilidad/iva" element={<Private><IvaPeriodo /></Private>} />
      <Route path="/contabilidad/cierre" element={<Private><Cierre /></Private>} />
      <Route path="/contabilidad/ctacte-credito" element={<Private><CtaCteContable /></Private>} />
      <Route path="/contabilidad/general" element={<Private><ContabilidadGeneral /></Private>} />
      <Route path="/caja/agencia-historico" element={<Private><AgenciaHistorico /></Private>} />

      {/* Seguros */}
      <Route path="/seguros/polizas" element={<Private><Polizas /></Private>} />
      <Route path="/seguros/regimenes" element={<Private><Regimenes /></Private>} />
      <Route path="/seguros/informes" element={<Private><InformesSeguros /></Private>} />
      <Route path="/seguros/adicional" element={<Private><SeguroAdicional /></Private>} />
      <Route path="/seguros/titulares" element={<Private><Titulares /></Private>} />

      {/* Despacho */}
      <Route path="/despacho/modelos" element={<Private><ModelosResolucion /></Private>} />
      <Route path="/despacho/resoluciones" element={<Private><Resoluciones /></Private>} />
      <Route path="/despacho/anexos" element={<Private><Anexos /></Private>} />
      <Route path="/despacho/expedientes" element={<Private><Expedientes /></Private>} />

      {/* Otros módulos */}
      <Route path="/juegos/liquidaciones" element={<Private><Juegos /></Private>} />
      <Route path="/juegos/maestro" element={<Private><MaestroJuegos /></Private>} />
      <Route path="/juegos/sorteos" element={<Private><ControlSorteos /></Private>} />
      <Route path="/juegos/ingresos" element={<Private><IngresosPorJuego /></Private>} />
      <Route path="/juegos/fondo-garantia" element={<Private><FondoGarantia /></Private>} />
      <Route path="/juegos" element={<Navigate to="/juegos/liquidaciones" />} />
      <Route path="/mesa/turnos" element={<Private><Mesa /></Private>} />
      <Route path="/mesa/tramites" element={<Private><Tramites /></Private>} />
      <Route path="/mesa/ingresados" element={<Private><TramitesIngresados /></Private>} />
      <Route path="/mesa" element={<Navigate to="/mesa/turnos" />} />

      {/* Clientes */}
      <Route path="/clientes/vision-360" element={<Private><Vision360 /></Private>} />
      <Route path="/clientes/maestro" element={<Private><Clientes /></Private>} />
      <Route path="/general/clientes" element={<Navigate to="/clientes/maestro" replace />} />

      {/* Seguridad (accesos, auditoría, migradores) */}
      <Route path="/seguridad/auditoria" element={<Private><Auditoria /></Private>} />
      <Route path="/seguridad/auditoria-cambios" element={<Private><AuditoriaCambios /></Private>} />
      <Route path="/seguridad/workflow" element={<Private><WorkflowAprobaciones /></Private>} />
      {/* Migradores y modelo de datos ahora viven bajo Controles de Versión */}
      <Route path="/controles-version/migradores" element={<Private><Migradores /></Private>} />
      <Route path="/controles-version/modelo-datos" element={<Private><ModeloDatos /></Private>} />
      <Route path="/seguridad/migradores" element={<Navigate to="/controles-version/migradores" replace />} />
      <Route path="/seguridad/modelo-datos" element={<Navigate to="/controles-version/modelo-datos" replace />} />
      <Route path="/general/auditoria" element={<Navigate to="/seguridad/auditoria" replace />} />

      {/* General / Tablas y maestros */}
      <Route path="/general/organismos" element={<Private><Organismos /></Private>} />
      <Route path="/general/oficinas" element={<Private><Oficinas /></Private>} />
      <Route path="/general/proveedores" element={<Private><Proveedores /></Private>} />
      <Route path="/general/companias" element={<Private><Companias /></Private>} />
      <Route path="/general/parametros" element={<Private><Parametros /></Private>} />

      <Route path="*" element={<Navigate to="/creditos/inbox-aprobaciones" />} />
    </Routes>
    </>
  );
}
