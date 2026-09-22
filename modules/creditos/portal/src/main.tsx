import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { iniciarTema } from "./tema";

// Antes del render: evita el destello claro cuando la preferencia guardada es oscura.
iniciarTema();

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
