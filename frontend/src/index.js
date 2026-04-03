import React from "react";
import ReactDOM from "react-dom/client";
import "./theme.css";   /* ← Global design tokens — edit here to reskin the whole app */
import "./index.css";
import App from "./App";

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
