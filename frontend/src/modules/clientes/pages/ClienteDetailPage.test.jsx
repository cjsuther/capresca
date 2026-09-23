import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ClienteDetailPage from "./ClienteDetailPage";
import { useAuthStore } from "../../../context/authStore";
import {
  getClient, getNotes, addNote,
  updateClient, updateHumanProfile, updateLegalProfile, updatePadron,
  getMembers, addMember, removeMember,
  searchClients, getCbus, addCbu, deleteCbu,
} from "../../../api/clientes";

vi.mock("../../../api/clientes", () => ({
  // Documentos del cliente: la sección arranca vacía salvo que el test diga otra cosa.
  getDocumentos: vi.fn(async () => ({ items: [] })),
  subirDocumento: vi.fn(), getDocumentoArchivo: vi.fn(), borrarDocumento: vi.fn(),
  getClient: vi.fn(),
  getNotes: vi.fn(),
  addNote: vi.fn(),
  updateClient: vi.fn(),
  updateHumanProfile: vi.fn(),
  updateLegalProfile: vi.fn(),
  updatePadron: vi.fn(),
  getMembers: vi.fn(),
  addMember: vi.fn(),
  removeMember: vi.fn(),
  searchClients: vi.fn(),
  getCbus: vi.fn(),
  addCbu: vi.fn(),
  deleteCbu: vi.fn(),
}));

const HUMANO = {
  id: 1,
  code: "CLI-0001",
  client_type: "HUMAN",
  email: "ana@correo.com",
  phone: "299-555",
  address: "San Martín 100",
  city: "Neuquén",
  country: "AR",
  is_active: true,
  human_profile: {
    first_name: "Ana", last_name: "Pérez",
    document_type: "DNI", document_number: "30111222",
    birth_date: "1990-01-01", nationality: "Argentina",
  },
};

// Cliente que vino de la importación del padrón: trae CUIL, domicilio completo, ficha de revista
// y los registros que la persona tenía en el sistema viejo (uno por organismo).
const IMPORTADO = {
  ...HUMANO,
  id: 3,
  code: "PAD20305047571",
  neighborhood: "CENTRO",
  department: "CAPITAL",
  postal_code: "K4700",
  human_profile: { ...HUMANO.human_profile, cuil: "20305047571" },
  padron: {
    organismo_numero: 13, organismo_codigo: "ACA", categoria: "AGENTE",
    sueldo: "910000.00", fecha_ingreso: "2005-03-01", beneficio: "BEN-1",
    sucursal: 2, cuenta: 4501, debito_automatico: true, situacion: 1,
    baja: false, motivo_baja: null,
  },
  legacy_refs: [
    { cidcliente: "ACA20305047571M", organismo_numero: 13, beneficio: null },
    { cidcliente: "AGJ20305047571M", organismo_numero: 9, beneficio: null },
  ],
};

const JURIDICO = {
  id: 2,
  code: "CLI-0002",
  client_type: "LEGAL",
  email: null, phone: null, address: null, city: null, country: null,
  is_active: false,
  legal_profile: {
    legal_name: "Agencia Sur SRL", trade_name: "Agencia Sur",
    tax_id_type: "CUIT", tax_id: "30711222333",
    legal_representative: "Ana Pérez", industry_sector: "Juegos",
    agency_number: "000042",
  },
};

const conPermisoEscritura = () =>
  useAuthStore.setState({
    token: "tok",
    user: { username: "ana" },
    permissions: { modules: ["clientes"], actions: { clientes: ["clients:read", "clients:write"] } },
  });

const soloLectura = () =>
  useAuthStore.setState({
    token: "tok",
    user: { username: "ana" },
    permissions: { modules: ["clientes"], actions: { clientes: ["clients:read"] } },
  });

function montar(id = "1") {
  return render(
    <MemoryRouter initialEntries={[`/modules/clientes/${id}`]}>
      <Routes>
        <Route path="/modules/clientes/:id" element={<ClienteDetailPage />} />
      </Routes>
    </MemoryRouter>
  );
}

// Los paneles de datos son tarjetas <div class="bg-surface ..."> con un <h3> adentro.
const panel = (titulo) => screen.getByRole("heading", { name: titulo }).closest("div.bg-surface");
const lapizDe = (titulo) => within(panel(titulo)).getAllByRole("button")[0];
const formularioDe = (placeholder) => screen.getByPlaceholderText(placeholder).closest("form");

describe("ClienteDetailPage — carga y datos", () => {
  beforeEach(() => {
    conPermisoEscritura();
    getClient.mockResolvedValue(HUMANO);
    getNotes.mockResolvedValue([]);
  });

  it("muestra 'Cargando...' hasta tener el cliente", async () => {
    let resolver;
    getClient.mockReturnValueOnce(new Promise((r) => { resolver = r; }));
    montar();
    expect(screen.getByText("Cargando...")).toBeInTheDocument();
    resolver(HUMANO);
    expect(await screen.findByText("Ana Pérez")).toBeInTheDocument();
  });

  it("pide el cliente y sus notas con el id de la URL", async () => {
    montar("77");
    await waitFor(() => expect(getClient).toHaveBeenCalledWith("77"));
    expect(getNotes).toHaveBeenCalledWith("77");
  });

  it("muestra los datos de la persona física y su estado", async () => {
    montar();
    expect(await screen.findByText("Ana Pérez")).toBeInTheDocument();
    expect(screen.getByText("CLI-0001")).toBeInTheDocument();
    expect(screen.getByText("Activo")).toBeInTheDocument();
    expect(screen.getByText("ana@correo.com")).toBeInTheDocument();
    expect(screen.getByText("30111222")).toBeInTheDocument();
    expect(screen.getByText("Datos personales")).toBeInTheDocument();
  });

  it("en persona física no aparecen miembros ni CBUs", async () => {
    montar();
    await screen.findByText("Ana Pérez");
    expect(screen.queryByText("Personas físicas vinculadas")).not.toBeInTheDocument();
    expect(screen.queryByText("CBUs registrados")).not.toBeInTheDocument();
    expect(getMembers).not.toHaveBeenCalled();
    expect(getCbus).not.toHaveBeenCalled();
  });

  it("muestra los datos de la empresa y marca inactivo", async () => {
    getClient.mockResolvedValue(JURIDICO);
    getMembers.mockResolvedValue([]);
    getCbus.mockResolvedValue([]);
    montar("2");

    expect(await screen.findByRole("heading", { name: "Agencia Sur SRL" })).toBeInTheDocument();
    expect(screen.getByText("Inactivo")).toBeInTheDocument();
    expect(screen.getByText("30711222333")).toBeInTheDocument();
    expect(screen.getByText("000042")).toBeInTheDocument();
    expect(screen.getByText("Datos de la empresa")).toBeInTheDocument();
    await waitFor(() => expect(getMembers).toHaveBeenCalledWith("2"));
    expect(getCbus).toHaveBeenCalledWith("2");
  });
});

describe("ClienteDetailPage — edición de datos", () => {
  beforeEach(() => {
    conPermisoEscritura();
    getClient.mockResolvedValue(HUMANO);
    getNotes.mockResolvedValue([]);
    updateClient.mockResolvedValue({});
    updateHumanProfile.mockResolvedValue({});
    updateLegalProfile.mockResolvedValue({});
  });

  it("edita y guarda los datos generales", async () => {
    const user = userEvent.setup();
    montar();
    await screen.findByText("Ana Pérez");

    await user.click(lapizDe("Datos generales"));
    const inputs = within(panel("Datos generales")).getAllByRole("textbox");
    await user.clear(inputs[0]);
    await user.type(inputs[0], "nueva@correo.com");
    await user.click(within(panel("Datos generales")).getByRole("button", { name: /Guardar/ }));

    await waitFor(() => expect(updateClient).toHaveBeenCalledTimes(1));
    expect(updateClient).toHaveBeenCalledWith("1", expect.objectContaining({
      email: "nueva@correo.com", city: "Neuquén", country: "AR",
    }));
    // al guardar se sale del modo edición y se recarga
    await waitFor(() => expect(getClient).toHaveBeenCalledTimes(2));
  });

  it("cancelar la edición recarga el cliente y descarta los cambios", async () => {
    const user = userEvent.setup();
    montar();
    await screen.findByText("Ana Pérez");

    await user.click(lapizDe("Datos generales"));
    const cancelar = within(panel("Datos generales")).getAllByRole("button")[1];
    await user.click(cancelar);

    await waitFor(() => expect(getClient).toHaveBeenCalledTimes(2));
    expect(updateClient).not.toHaveBeenCalled();
    expect(await screen.findByText("ana@correo.com")).toBeInTheDocument();
  });

  it("muestra el detalle del backend si falla el guardado", async () => {
    updateClient.mockRejectedValue({ response: { data: { detail: "Email ya usado" } } });
    const user = userEvent.setup();
    montar();
    await screen.findByText("Ana Pérez");

    await user.click(lapizDe("Datos generales"));
    await user.click(within(panel("Datos generales")).getByRole("button", { name: /Guardar/ }));

    expect(await screen.findByText("Email ya usado")).toBeInTheDocument();
  });

  it("muestra un mensaje genérico si el error no trae detalle", async () => {
    updateHumanProfile.mockRejectedValue(new Error("sin red"));
    const user = userEvent.setup();
    montar();
    await screen.findByText("Ana Pérez");

    await user.click(lapizDe("Datos personales"));
    await user.click(within(panel("Datos personales")).getByRole("button", { name: /Guardar/ }));

    expect(await screen.findByText("Error al guardar")).toBeInTheDocument();
  });

  it("guarda el perfil de persona física por el endpoint /human", async () => {
    const user = userEvent.setup();
    montar();
    await screen.findByText("Ana Pérez");

    await user.click(lapizDe("Datos personales"));
    const inputs = within(panel("Datos personales")).getAllByRole("textbox");
    await user.clear(inputs[0]);
    await user.type(inputs[0], "Anabel");
    await user.click(within(panel("Datos personales")).getByRole("button", { name: /Guardar/ }));

    await waitFor(() => expect(updateHumanProfile).toHaveBeenCalledTimes(1));
    expect(updateHumanProfile).toHaveBeenCalledWith("1", expect.objectContaining({ first_name: "Anabel" }));
    expect(updateLegalProfile).not.toHaveBeenCalled();
  });

  it("guarda el perfil de empresa por el endpoint /legal", async () => {
    getClient.mockResolvedValue(JURIDICO);
    getMembers.mockResolvedValue([]);
    getCbus.mockResolvedValue([]);
    const user = userEvent.setup();
    montar("2");
    await screen.findByRole("heading", { name: "Agencia Sur SRL" });

    await user.click(lapizDe("Datos de la empresa"));
    await user.click(within(panel("Datos de la empresa")).getByRole("button", { name: /Guardar/ }));

    await waitFor(() => expect(updateLegalProfile).toHaveBeenCalledTimes(1));
    expect(updateLegalProfile).toHaveBeenCalledWith("2", expect.objectContaining({ legal_name: "Agencia Sur SRL" }));
    expect(updateHumanProfile).not.toHaveBeenCalled();
  });

  it("sin permiso clients:write no se puede editar nada", async () => {
    soloLectura();
    montar();
    await screen.findByText("Ana Pérez");
    expect(within(panel("Datos generales")).queryByRole("button")).not.toBeInTheDocument();
    expect(within(panel("Datos personales")).queryByRole("button")).not.toBeInTheDocument();
  });
});

describe("ClienteDetailPage — notas", () => {
  beforeEach(() => {
    conPermisoEscritura();
    getClient.mockResolvedValue(HUMANO);
    getNotes.mockResolvedValue([]);
    addNote.mockResolvedValue({});
  });

  it("avisa cuando no hay notas", async () => {
    montar();
    expect(await screen.findByText("Sin notas")).toBeInTheDocument();
  });

  it("lista las notas existentes", async () => {
    getNotes.mockResolvedValue([{ id: 1, content: "Llamar mañana", created_at: "2026-01-02T10:00:00Z" }]);
    montar();
    expect(await screen.findByText("Llamar mañana")).toBeInTheDocument();
    expect(screen.queryByText("Sin notas")).not.toBeInTheDocument();
  });

  it("agrega una nota, limpia el campo y recarga el listado", async () => {
    const user = userEvent.setup();
    montar();
    await screen.findByText("Ana Pérez");

    const input = screen.getByPlaceholderText("Agregar nota...");
    await user.type(input, "Envió documentación");
    await user.click(within(formularioDe("Agregar nota...")).getByRole("button", { name: "Agregar" }));

    await waitFor(() => expect(addNote).toHaveBeenCalledWith("1", "Envió documentación"));
    await waitFor(() => expect(input).toHaveValue(""));
    expect(getNotes).toHaveBeenCalledTimes(2);
  });

  it("no llama a la API si la nota está vacía o en blanco", async () => {
    const user = userEvent.setup();
    montar();
    await screen.findByText("Ana Pérez");

    await user.type(screen.getByPlaceholderText("Agregar nota..."), "   ");
    await user.click(within(formularioDe("Agregar nota...")).getByRole("button", { name: "Agregar" }));
    expect(addNote).not.toHaveBeenCalled();
  });
});

describe("ClienteDetailPage — CBUs (solo persona jurídica)", () => {
  beforeEach(() => {
    conPermisoEscritura();
    getClient.mockResolvedValue(JURIDICO);
    getNotes.mockResolvedValue([]);
    getMembers.mockResolvedValue([]);
    getCbus.mockResolvedValue([]);
    addCbu.mockResolvedValue({});
    deleteCbu.mockResolvedValue({});
  });

  it("avisa cuando no hay CBUs cargados", async () => {
    montar("2");
    expect(await screen.findByText("Sin CBUs registrados")).toBeInTheDocument();
  });

  it("lista los CBUs con su alias", async () => {
    getCbus.mockResolvedValue([{ id: 5, cbu: "1".repeat(22), alias: "agencia.sur" }]);
    montar("2");
    expect(await screen.findByText("1".repeat(22))).toBeInTheDocument();
    expect(screen.getByText("agencia.sur")).toBeInTheDocument();
  });

  it("rechaza un CBU que no tenga 22 dígitos", async () => {
    const user = userEvent.setup();
    montar("2");
    await screen.findByRole("heading", { name: "Agencia Sur SRL" });

    await user.type(screen.getByPlaceholderText("CBU (22 dígitos)"), "12345");
    fireEvent.submit(formularioDe("CBU (22 dígitos)"));

    expect(await screen.findByText("El CBU debe tener exactamente 22 dígitos")).toBeInTheDocument();
    expect(addCbu).not.toHaveBeenCalled();
  });

  it("descarta los caracteres no numéricos que se tipean en el CBU", async () => {
    const user = userEvent.setup();
    montar("2");
    await screen.findByRole("heading", { name: "Agencia Sur SRL" });

    const input = screen.getByPlaceholderText("CBU (22 dígitos)");
    await user.type(input, "01-70-abc99");
    expect(input).toHaveValue("017099");
  });

  it("agrega un CBU válido con alias y recarga la lista", async () => {
    const user = userEvent.setup();
    montar("2");
    await screen.findByRole("heading", { name: "Agencia Sur SRL" });

    await user.type(screen.getByPlaceholderText("CBU (22 dígitos)"), "0".repeat(22));
    await user.type(screen.getByPlaceholderText("Alias (opcional)"), "agencia.sur");
    fireEvent.submit(formularioDe("CBU (22 dígitos)"));

    await waitFor(() =>
      expect(addCbu).toHaveBeenCalledWith("2", { cbu: "0".repeat(22), alias: "agencia.sur" })
    );
    await waitFor(() => expect(getCbus).toHaveBeenCalledTimes(2));
    expect(screen.getByPlaceholderText("CBU (22 dígitos)")).toHaveValue("");
  });

  it("manda alias null cuando se deja vacío", async () => {
    const user = userEvent.setup();
    montar("2");
    await screen.findByRole("heading", { name: "Agencia Sur SRL" });

    await user.type(screen.getByPlaceholderText("CBU (22 dígitos)"), "9".repeat(22));
    fireEvent.submit(formularioDe("CBU (22 dígitos)"));

    await waitFor(() => expect(addCbu).toHaveBeenCalledWith("2", { cbu: "9".repeat(22), alias: null }));
  });

  it("muestra el error del backend al agregar un CBU", async () => {
    addCbu.mockRejectedValue({ response: { data: { detail: "CBU ya registrado" } } });
    const user = userEvent.setup();
    montar("2");
    await screen.findByRole("heading", { name: "Agencia Sur SRL" });

    await user.type(screen.getByPlaceholderText("CBU (22 dígitos)"), "0".repeat(22));
    fireEvent.submit(formularioDe("CBU (22 dígitos)"));

    expect(await screen.findByText("CBU ya registrado")).toBeInTheDocument();
  });

  it("elimina un CBU previa confirmación", async () => {
    getCbus.mockResolvedValue([{ id: 5, cbu: "1".repeat(22), alias: null }]);
    const confirmar = vi.spyOn(window, "confirm").mockReturnValue(true);
    const user = userEvent.setup();
    montar("2");

    const fila = (await screen.findByText("1".repeat(22))).closest("div.bg-gray-50");
    await user.click(within(fila).getByRole("button"));

    expect(confirmar).toHaveBeenCalledWith("¿Eliminar este CBU?");
    await waitFor(() => expect(deleteCbu).toHaveBeenCalledWith("2", 5));
    confirmar.mockRestore();
  });

  it("si se cancela la confirmación no elimina nada", async () => {
    getCbus.mockResolvedValue([{ id: 5, cbu: "1".repeat(22), alias: null }]);
    const confirmar = vi.spyOn(window, "confirm").mockReturnValue(false);
    const user = userEvent.setup();
    montar("2");

    const fila = (await screen.findByText("1".repeat(22))).closest("div.bg-gray-50");
    await user.click(within(fila).getByRole("button"));

    expect(deleteCbu).not.toHaveBeenCalled();
    confirmar.mockRestore();
  });

  it("muestra el error del backend al eliminar un CBU", async () => {
    getCbus.mockResolvedValue([{ id: 5, cbu: "1".repeat(22), alias: null }]);
    deleteCbu.mockRejectedValue({ response: { data: { detail: "CBU en uso" } } });
    const confirmar = vi.spyOn(window, "confirm").mockReturnValue(true);
    const user = userEvent.setup();
    montar("2");

    const fila = (await screen.findByText("1".repeat(22))).closest("div.bg-gray-50");
    await user.click(within(fila).getByRole("button"));

    expect(await screen.findByText("CBU en uso")).toBeInTheDocument();
    confirmar.mockRestore();
  });

  it("sin permiso de escritura no aparece el alta de CBU pero sí el listado", async () => {
    soloLectura();
    getCbus.mockResolvedValue([{ id: 5, cbu: "1".repeat(22), alias: null }]);
    montar("2");

    expect(await screen.findByText("1".repeat(22))).toBeInTheDocument();
    expect(screen.queryByPlaceholderText("CBU (22 dígitos)")).not.toBeInTheDocument();
  });
});

describe("ClienteDetailPage — miembros (solo persona jurídica)", () => {
  const PERSONA = {
    id: 8,
    code: "CLI-0008",
    client_type: "HUMAN",
    human_profile: { first_name: "Juan", last_name: "Gómez", document_type: "DNI", document_number: "20333444" },
  };

  beforeEach(() => {
    conPermisoEscritura();
    getClient.mockResolvedValue(JURIDICO);
    getNotes.mockResolvedValue([]);
    getCbus.mockResolvedValue([]);
    getMembers.mockResolvedValue([]);
    addMember.mockResolvedValue({});
    removeMember.mockResolvedValue({});
    searchClients.mockResolvedValue({ data: [PERSONA, { id: 9, client_type: "LEGAL", legal_profile: {} }] });
  });

  it("avisa cuando no hay personas vinculadas", async () => {
    montar("2");
    expect(await screen.findByText("Sin personas físicas vinculadas")).toBeInTheDocument();
  });

  it("lista los miembros con documento y rol", async () => {
    getMembers.mockResolvedValue([{ id: 3, role: "Titular", human_client: { human_profile: PERSONA.human_profile } }]);
    montar("2");
    expect(await screen.findByText("Juan Gómez")).toBeInTheDocument();
    expect(screen.getByText("DNI 20333444")).toBeInTheDocument();
    expect(screen.getByText("Titular")).toBeInTheDocument();
  });

  it("no busca con menos de 2 caracteres", async () => {
    const user = userEvent.setup();
    montar("2");
    await screen.findByRole("heading", { name: "Agencia Sur SRL" });

    await user.type(screen.getByPlaceholderText("Buscar por nombre o documento..."), "j");
    expect(searchClients).not.toHaveBeenCalled();
  });

  it("busca y ofrece sólo personas físicas", async () => {
    const user = userEvent.setup();
    montar("2");
    await screen.findByRole("heading", { name: "Agencia Sur SRL" });

    await user.type(screen.getByPlaceholderText("Buscar por nombre o documento..."), "ju");
    await waitFor(() => expect(searchClients).toHaveBeenCalledWith("ju"));
    expect(await screen.findByRole("button", { name: /Juan Gómez/ })).toBeInTheDocument();
    expect(screen.getByText("20333444")).toBeInTheDocument();
    // el resultado de tipo LEGAL quedó filtrado: sólo hay una opción en el desplegable
    const desplegable = screen.getByRole("button", { name: /Juan Gómez/ }).parentElement;
    expect(within(desplegable).getAllByRole("button")).toHaveLength(1);
  });

  it("selecciona una persona y la agrega con rol", async () => {
    const user = userEvent.setup();
    montar("2");
    await screen.findByRole("heading", { name: "Agencia Sur SRL" });

    const buscador = screen.getByPlaceholderText("Buscar por nombre o documento...");
    await user.type(buscador, "ju");
    await user.click(await screen.findByRole("button", { name: /Juan Gómez/ }));
    expect(buscador).toHaveValue("Juan Gómez");

    await user.type(screen.getByPlaceholderText("Rol (opcional)"), "Apoderado");
    const zona = screen.getByPlaceholderText("Rol (opcional)").parentElement;
    await user.click(within(zona).getByRole("button", { name: "Agregar" }));

    await waitFor(() =>
      expect(addMember).toHaveBeenCalledWith("2", { human_client_id: 8, role: "Apoderado" })
    );
    await waitFor(() => expect(getMembers).toHaveBeenCalledTimes(2));
    expect(buscador).toHaveValue("");
  });

  it("manda rol null si no se completa", async () => {
    const user = userEvent.setup();
    montar("2");
    await screen.findByRole("heading", { name: "Agencia Sur SRL" });

    await user.type(screen.getByPlaceholderText("Buscar por nombre o documento..."), "ju");
    await user.click(await screen.findByRole("button", { name: /Juan Gómez/ }));
    const zona = screen.getByPlaceholderText("Rol (opcional)").parentElement;
    await user.click(within(zona).getByRole("button", { name: "Agregar" }));

    await waitFor(() => expect(addMember).toHaveBeenCalledWith("2", { human_client_id: 8, role: null }));
  });

  it("el botón Agregar está deshabilitado mientras no haya nadie seleccionado", async () => {
    montar("2");
    await screen.findByRole("heading", { name: "Agencia Sur SRL" });
    const zona = screen.getByPlaceholderText("Rol (opcional)").parentElement;
    expect(within(zona).getByRole("button", { name: "Agregar" })).toBeDisabled();
  });

  it("permite deseleccionar la persona elegida", async () => {
    const user = userEvent.setup();
    montar("2");
    await screen.findByRole("heading", { name: "Agencia Sur SRL" });

    const buscador = screen.getByPlaceholderText("Buscar por nombre o documento...");
    await user.type(buscador, "ju");
    await user.click(await screen.findByRole("button", { name: /Juan Gómez/ }));

    const zona = screen.getByPlaceholderText("Rol (opcional)").parentElement;
    const botones = within(zona).getAllByRole("button");
    await user.click(botones[botones.length - 1]);   // la X de limpiar
    expect(buscador).toHaveValue("");
    expect(within(zona).getByRole("button", { name: "Agregar" })).toBeDisabled();
  });

  it("muestra el error del backend al agregar un miembro", async () => {
    addMember.mockRejectedValue({ response: { data: { detail: "Ya es miembro" } } });
    const user = userEvent.setup();
    montar("2");
    await screen.findByRole("heading", { name: "Agencia Sur SRL" });

    await user.type(screen.getByPlaceholderText("Buscar por nombre o documento..."), "ju");
    await user.click(await screen.findByRole("button", { name: /Juan Gómez/ }));
    const zona = screen.getByPlaceholderText("Rol (opcional)").parentElement;
    await user.click(within(zona).getByRole("button", { name: "Agregar" }));

    expect(await screen.findByText("Ya es miembro")).toBeInTheDocument();
  });

  it("quita un miembro previa confirmación", async () => {
    getMembers.mockResolvedValue([{ id: 3, role: null, human_client: { human_profile: PERSONA.human_profile } }]);
    const confirmar = vi.spyOn(window, "confirm").mockReturnValue(true);
    const user = userEvent.setup();
    montar("2");

    const fila = (await screen.findByText("Juan Gómez")).closest("div.bg-gray-50");
    await user.click(within(fila).getByRole("button"));

    expect(confirmar).toHaveBeenCalledWith("¿Quitar este miembro?");
    await waitFor(() => expect(removeMember).toHaveBeenCalledWith("2", 3));
    confirmar.mockRestore();
  });

  it("si se cancela la confirmación no quita al miembro", async () => {
    getMembers.mockResolvedValue([{ id: 3, role: null, human_client: { human_profile: PERSONA.human_profile } }]);
    const confirmar = vi.spyOn(window, "confirm").mockReturnValue(false);
    const user = userEvent.setup();
    montar("2");

    const fila = (await screen.findByText("Juan Gómez")).closest("div.bg-gray-50");
    await user.click(within(fila).getByRole("button"));

    expect(removeMember).not.toHaveBeenCalled();
    confirmar.mockRestore();
  });

  it("muestra el error del backend al quitar un miembro", async () => {
    getMembers.mockResolvedValue([{ id: 3, role: null, human_client: { human_profile: PERSONA.human_profile } }]);
    removeMember.mockRejectedValue(new Error("sin red"));
    const confirmar = vi.spyOn(window, "confirm").mockReturnValue(true);
    const user = userEvent.setup();
    montar("2");

    const fila = (await screen.findByText("Juan Gómez")).closest("div.bg-gray-50");
    await user.click(within(fila).getByRole("button"));

    expect(await screen.findByText("Error al quitar miembro")).toBeInTheDocument();
    confirmar.mockRestore();
  });

  it("sin permiso de escritura no aparece el buscador ni el botón de quitar", async () => {
    soloLectura();
    getMembers.mockResolvedValue([{ id: 3, role: null, human_client: { human_profile: PERSONA.human_profile } }]);
    montar("2");

    expect(await screen.findByText("Juan Gómez")).toBeInTheDocument();
    expect(screen.queryByPlaceholderText("Buscar por nombre o documento...")).not.toBeInTheDocument();
    const fila = screen.getByText("Juan Gómez").closest("div.bg-gray-50");
    expect(within(fila).queryByRole("button")).not.toBeInTheDocument();
  });

  // ── Padrón del sistema anterior ─────────────────────────────────────────
  it("muestra la ficha del padrón y los registros del sistema viejo", async () => {
    getClient.mockResolvedValue(IMPORTADO);
    montar("3");

    expect(await screen.findByText("Padrón (sistema anterior)")).toBeInTheDocument();
    expect(screen.getByText("13")).toBeInTheDocument();          // organismo
    expect(screen.getByText("ACA")).toBeInTheDocument();
    expect(screen.getByText("AGENTE")).toBeInTheDocument();
    expect(screen.getByText("$ 910.000,00")).toBeInTheDocument();
    expect(screen.getByText("4501")).toBeInTheDocument();         // cuenta
    expect(screen.getByText("Sí")).toBeInTheDocument();           // débito automático
    expect(screen.getByText(/Registros que tenía en el sistema anterior \(2\)/)).toBeInTheDocument();
    expect(screen.getByText(/ACA20305047571M/)).toBeInTheDocument();
    expect(screen.getByText(/AGJ20305047571M · org 9/)).toBeInTheDocument();
  });

  it("muestra el CUIL y el domicilio completo del padrón", async () => {
    getClient.mockResolvedValue(IMPORTADO);
    montar("3");

    expect(await screen.findByText("20305047571")).toBeInTheDocument();
    expect(screen.getByText("CENTRO")).toBeInTheDocument();
    expect(screen.getByText("CAPITAL")).toBeInTheDocument();
    expect(screen.getByText("K4700")).toBeInTheDocument();
  });

  it("un cliente cargado a mano no muestra la ficha de padrón", async () => {
    getClient.mockResolvedValue(HUMANO);
    montar();
    await screen.findByText("Ana Pérez");
    expect(screen.queryByText("Padrón (sistema anterior)")).not.toBeInTheDocument();
  });

  it("avisa cuando la persona está dada de baja en el padrón", async () => {
    getClient.mockResolvedValue({
      ...IMPORTADO,
      padron: { ...IMPORTADO.padron, baja: true, motivo_baja: "RENUNCIA" },
    });
    montar("3");
    expect(await screen.findByText("Dado de baja: RENUNCIA")).toBeInTheDocument();
  });

  // ── Validaciones, combos y fechas de "Datos personales" ─────────────────
  const editarPerfil = async (user) => {
    await user.click(lapizDe("Datos personales"));
    return panel("Datos personales");
  };

  it("el tipo de documento y el sexo son listas, y el nacimiento un selector de fecha", async () => {
    const user = userEvent.setup();
    getClient.mockResolvedValue({ ...HUMANO, human_profile: { ...HUMANO.human_profile, gender: "F" } });
    montar();
    await screen.findByText("Ana Pérez");
    const ficha = await editarPerfil(user);

    const tipoDoc = within(ficha).getByLabelText("Tipo doc.");
    expect(tipoDoc.tagName).toBe("SELECT");
    expect([...tipoDoc.options].map((o) => o.value)).toContain("PASAPORTE");

    const sexo = within(ficha).getByLabelText("Sexo");
    expect(sexo.tagName).toBe("SELECT");
    expect(sexo.value).toBe("F");

    const nacimiento = within(ficha).getByLabelText("Nacimiento");
    expect(nacimiento).toHaveAttribute("type", "date");
    expect(nacimiento).toHaveAttribute("max");      // no deja elegir una fecha futura
  });

  it("fuera de edición el combo se ve con su etiqueta, no con el código", async () => {
    getClient.mockResolvedValue({ ...HUMANO, human_profile: { ...HUMANO.human_profile, gender: "F" } });
    montar();
    expect(await screen.findByText("Femenino")).toBeInTheDocument();
  });

  it("no guarda un CUIL inválido y lo marca", async () => {
    const user = userEvent.setup();
    getClient.mockResolvedValue(HUMANO);
    montar();
    await screen.findByText("Ana Pérez");
    const ficha = await editarPerfil(user);

    const cuil = within(ficha).getByLabelText("CUIL");
    await user.clear(cuil);
    await user.type(cuil, "20305047572");           // dígito verificador equivocado
    expect(await within(ficha).findByText(/El CUIL no es válido/)).toBeInTheDocument();

    await user.click(within(ficha).getByRole("button", { name: /Guardar/ }));
    expect(updateHumanProfile).not.toHaveBeenCalled();
    expect(await screen.findByText(/Revisá los datos marcados en rojo/)).toBeInTheDocument();
  });

  it("no guarda sin nombre ni con una fecha de nacimiento futura", async () => {
    const user = userEvent.setup();
    getClient.mockResolvedValue(HUMANO);
    montar();
    await screen.findByText("Ana Pérez");
    const ficha = await editarPerfil(user);

    await user.clear(within(ficha).getByLabelText("Nombre"));
    expect(await within(ficha).findByText(/nombre es obligatorio/)).toBeInTheDocument();
    await user.click(within(ficha).getByRole("button", { name: /Guardar/ }));
    expect(updateHumanProfile).not.toHaveBeenCalled();
  });

  // Los 56 CUIL que el padrón viejo trae mal no pueden trabar la corrección de otro campo.
  it("un CUIL que ya venía mal se avisa pero deja guardar otro campo", async () => {
    const user = userEvent.setup();
    getClient.mockResolvedValue({
      ...HUMANO, human_profile: { ...HUMANO.human_profile, cuil: "20305047572" },
    });
    updateHumanProfile.mockResolvedValue({});
    montar();
    await screen.findByText("Ana Pérez");
    const ficha = await editarPerfil(user);

    expect(await within(ficha).findByText(/El CUIL no es válido/)).toBeInTheDocument();
    const nombre = within(ficha).getByLabelText("Nombre");
    await user.clear(nombre);
    await user.type(nombre, "Anabel");
    await user.click(within(ficha).getByRole("button", { name: /Guardar/ }));

    await waitFor(() => expect(updateHumanProfile).toHaveBeenCalledTimes(1));
  });

  it("la empresa valida el CUIT y tiene fecha de constitución", async () => {
    const user = userEvent.setup();
    getClient.mockResolvedValue(JURIDICO);
    getMembers.mockResolvedValue([]);
    getCbus.mockResolvedValue([]);
    montar("2");
    await screen.findByRole("heading", { name: "Agencia Sur SRL" });

    await user.click(lapizDe("Datos de la empresa"));
    const ficha = panel("Datos de la empresa");
    expect(within(ficha).getByLabelText("Constitución")).toHaveAttribute("type", "date");
    expect(within(ficha).getByLabelText("Tipo ID fiscal").tagName).toBe("SELECT");

    const cuit = within(ficha).getByLabelText("ID Fiscal");
    await user.clear(cuit);
    await user.type(cuit, "30711222334");
    expect(await within(ficha).findByText(/El CUIT no es válido/)).toBeInTheDocument();
    await user.click(within(ficha).getByRole("button", { name: /Guardar/ }));
    expect(updateLegalProfile).not.toHaveBeenCalled();
  });

  it("la ficha del padrón se puede corregir", async () => {
    const user = userEvent.setup();
    getClient.mockResolvedValue(IMPORTADO);
    updatePadron.mockResolvedValue(IMPORTADO);
    montar("3");
    await screen.findByText("Padrón (sistema anterior)");

    await user.click(screen.getByRole("button", { name: "Editar padrón" }));
    const categoria = screen.getByLabelText("Categoría");
    await user.clear(categoria);
    await user.type(categoria, "JEFE DE DEPARTAMENTO");
    expect(screen.getByLabelText("Ingreso")).toHaveAttribute("type", "date");
    await user.selectOptions(screen.getByLabelText("Débito automático"), "false");

    await user.click(screen.getAllByRole("button", { name: /Guardar/ })[0]);
    await waitFor(() => expect(updatePadron).toHaveBeenCalledTimes(1));
    expect(updatePadron).toHaveBeenCalledWith("3", expect.objectContaining({
      categoria: "JEFE DE DEPARTAMENTO", debito_automatico: false,
    }));
  });

  it("no guarda la ficha con un sueldo que no es número", async () => {
    const user = userEvent.setup();
    getClient.mockResolvedValue(IMPORTADO);
    montar("3");
    await screen.findByText("Padrón (sistema anterior)");

    await user.click(screen.getByRole("button", { name: "Editar padrón" }));
    const sueldo = screen.getByLabelText("Sueldo");
    await user.clear(sueldo);
    await user.type(sueldo, "mil pesos");
    await user.click(screen.getAllByRole("button", { name: /Guardar/ })[0]);

    expect(await screen.findByText(/El sueldo tiene que ser un número/)).toBeInTheDocument();
    expect(updatePadron).not.toHaveBeenCalled();
  });
});
