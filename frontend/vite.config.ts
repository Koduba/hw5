import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The desk runs on http://localhost:5173 and calls the FastAPI backend at
// http://localhost:8000 directly (see src/api.ts; override with VITE_API_URL).
// `npm run dev` opens the desk in your browser.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, strictPort: true, open: true },
});
