import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";
import { iniciarTema } from "./context/themeStore";

// El tema se aplica antes del primer render para no mostrar un flash claro en modo oscuro.
iniciarTema();

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
