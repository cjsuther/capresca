import CuotasMoraPage from "./pages/creditos/CuotasMoraPage";
import PendientesCobroPage from "./pages/creditos/PendientesCobroPage";
import EnviosPadronPage from "./pages/creditos/EnviosPadronPage";
import JubiladosPage from "./pages/creditos/JubiladosPage";
import EstadisticasCarteraPage from "./pages/creditos/EstadisticasCarteraPage";
import PorCarteraPage from "./pages/creditos/PorCarteraPage";
import SinDebitoPage from "./pages/creditos/SinDebitoPage";
import PagosEnCajaPage from "./pages/creditos/PagosEnCajaPage";
import ListadoCreditosPage from "./pages/creditos/ListadoCreditosPage";
import SituacionClientePage from "./pages/creditos/SituacionClientePage";
import CuentaCorrientePage from "./pages/creditos/CuentaCorrientePage";
import ResumenCobrosPage from "./pages/creditos/ResumenCobrosPage";
import InformeCreditosPage from "./pages/creditos/InformeCreditosPage";
import BajaCreditoPage from "./pages/creditos/BajaCreditoPage";
import CancelacionCreditoPage from "./pages/creditos/CancelacionCreditoPage";
import RecalculoCreditoPage from "./pages/creditos/RecalculoCreditoPage";
import TurnosOtorgadosPage from "./pages/creditos/TurnosOtorgadosPage";
import LineasCreditoPage from "./pages/creditos/LineasCreditoPage";
import ParametrosCreditosPage from "./pages/creditos/ParametrosCreditosPage";
import SimuladorPage from "./pages/creditos/SimuladorPage";
import TurnosAdminPage from "./pages/creditos/TurnosAdminPage";
import LiquidacionLotePage from "./pages/creditos/LiquidacionLotePage";
import CajaCreditosPage from "./pages/creditos/CajaCreditosPage";
import SolicitudesPage from "./pages/creditos/SolicitudesPage";
import InboxAprobacionesPage from "./pages/creditos/InboxAprobacionesPage";
import SistemaCalculosPage from "./pages/creditos/SistemaCalculosPage";
import TableroCarteraPage from "./pages/creditos/TableroCarteraPage";
import SituacionClienteLineaPage from "./pages/creditos/SituacionClienteLineaPage";
import SolicitudesCreditoPage from "./pages/creditos/SolicitudesCreditoPage";
import ConfigurarCreditosPage from "./pages/creditos/ConfigurarCreditosPage";

/** Pantallas del módulo, por ruta del menú. */
export const RUTAS = {
  "tablero-cartera": TableroCarteraPage,
  "mora": CuotasMoraPage,
  "pendientes": PendientesCobroPage,
  "envios": EnviosPadronPage,
  "jubilados": JubiladosPage,
  "estadisticas": EstadisticasCarteraPage,
  "por-cartera": PorCarteraPage,
  "sin-debito": SinDebitoPage,
  "pagos-caja": PagosEnCajaPage,
  "listado": ListadoCreditosPage,
  "situacion": SituacionClientePage,
  "situacion-linea": SituacionClienteLineaPage,
  "cuenta-corriente": CuentaCorrientePage,
  "resumen-cobros": ResumenCobrosPage,
  "informe": InformeCreditosPage,
  "baja": BajaCreditoPage,
  "cancelacion": CancelacionCreditoPage,
  "recalculo": RecalculoCreditoPage,
  "turnos": TurnosOtorgadosPage,
  "configurar": ConfigurarCreditosPage,
  "lineas": LineasCreditoPage,
  "parametros": ParametrosCreditosPage,
  "simulador": SimuladorPage,
  "turnos-admin": TurnosAdminPage,
  "liquidacion-lote": LiquidacionLotePage,
  "caja": CajaCreditosPage,
  "solicitudes-credito": SolicitudesCreditoPage,
  "solicitudes": SolicitudesPage,
  "inbox-aprobaciones": InboxAprobacionesPage,
  "sistema-calculos": SistemaCalculosPage,
};

/** Pantalla a la que entra el módulo por defecto. */
export const primeraRuta = () => Object.keys(RUTAS)[0] || null;
