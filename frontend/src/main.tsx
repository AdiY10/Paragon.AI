import "vite/modulepreload-polyfill";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { App } from "./app/App";
import { queryClient } from "./app/queryClient";
import { installRouter } from "./app/router";
import "./styles/tokens.css";
import "./styles/base.css";
import "./styles/legacy.css";
import "./styles/layout.css";
import "./styles/components.css";
import "./styles/charts.css";
import "./styles/map.css";
import "./styles/properties.css";
import "./styles/analysis.css";
import "./styles/analyze.css";

installRouter();
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
);
