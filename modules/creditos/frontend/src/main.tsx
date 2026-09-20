import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    {/* Portezuelo publica esta app bajo /creditos/ (ver vite.config.ts → base). */}
    <BrowserRouter basename="/creditos">
      <App />
    </BrowserRouter>
  </React.StrictMode>
);
