import { describe, expect, it } from "vitest";
import { accionPendiente, csvReporte, reporteEnvio } from "./reporteEnvio";

const NO_HAB = "1078 - El operador no tiene acceso o no existe la cuenta crédito";
const pago = (id, estado, extra = {}) => ({
  id, beneficiario: `BENEF ${id}`, documento: "20301234569", cbu: `00700238300040265195${String(id).padStart(2, "0")}`,
  monto: 100, concepto: "Desembolso", estado, motivo: "", id_operacion_ib: "", enviado_por: "teso", ...extra,
});
const LOTE = {
  codigo: "LOT-2026-00007", descripcion: "OP-2026-00001", enviado_por: "teso", enviado_en: "2026-10-16T12:00:00",
  cuenta_origen: { bank_number: "011", account_number: "31554660051353", account_type: "CC" },
  pagos: [
    pago(1, "ENVIADO", { id_operacion_ib: "OP-1" }),
    pago(2, "FALLIDO", { motivo: NO_HAB, cuenta_sin_habilitar: "DESTINO" }),
    pago(3, "FALLIDO", { motivo: NO_HAB, cuenta_sin_habilitar: "DESTINO", cbu: pago(2).cbu, monto: 50 }),
    pago(4, "INCIERTO", { motivo: "Sin respuesta" }),
    pago(5, "EXCLUIDO"),
  ],
};

describe("reporteEnvio", () => {
  it("separa realizadas y no realizadas y junta las cuentas a habilitar por CBU", () => {
    const r = reporteEnvio(LOTE);
    expect(r.realizadas.map((p) => p.id)).toEqual([1]);
    expect(r.noRealizadas.map((p) => p.id)).toEqual([2, 3, 4]);
    expect(r.totalNoRealizadas).toBe(250);
    expect(r.cuentasAHabilitar).toEqual([{ cbu: pago(2).cbu, beneficiario: "BENEF 2", documento: "20301234569" }]);
    expect(r.fallidos).toBe(2);
    expect(r.origenSinHabilitar).toBe(false);
  });

  it("dice qué hacer con cada pago que no salió", () => {
    expect(accionPendiente(LOTE.pagos[1], "portezuelo")).toBe("Dar de alta el CBU en Interbanking y habilitarlo para el operador portezuelo");
    expect(accionPendiente({ estado: "FALLIDO", cuenta_sin_habilitar: "ORIGEN" })).toBe("Habilitar la cuenta de origen para el operador de API");
    expect(accionPendiente(LOTE.pagos[3])).toMatch(/no reintentar/);
    expect(accionPendiente({ estado: "FALLIDO", motivo: "CBU inexistente" })).toBe("Revisar el motivo y reintentar");
  });

  it("arma el CSV con encabezado, una fila por pago enviado y el CBU como texto", () => {
    const lineas = csvReporte(LOTE, "portezuelo").split("\r\n");
    expect(lineas[0]).toBe("Reporte de envío del lote;LOT-2026-00007");
    expect(lineas).toContain("Cuenta de origen;011/31554660051353/CC");
    expect(lineas).toContain("Operador de API de Interbanking;portezuelo");
    const filas = lineas.slice(lineas.indexOf("") + 2);
    expect(filas).toHaveLength(4);                                     // el excluido no se envió: no figura
    expect(filas[0]).toMatch(/^Realizada;BENEF 1;="20301234569";="0070023830004026519501";007;100,00;/);
    expect(filas[1]).toContain("No realizada;BENEF 2");
    expect(filas[1]).toContain("Dar de alta el CBU en Interbanking y habilitarlo para el operador portezuelo");
  });
});
