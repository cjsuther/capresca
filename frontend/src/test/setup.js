import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

import api from "../api/client";

// Ningún test sale a la red: por defecto toda request responde vacío. Cada test mockea lo que necesita.
api.defaults.adapter = async (config) => ({
  data: {}, status: 200, statusText: "OK", headers: {}, config,
});

afterEach(() => {
  cleanup();
  sessionStorage.clear();
  localStorage.clear();
  vi.clearAllMocks();
});
