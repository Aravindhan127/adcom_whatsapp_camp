/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BACKEND_URL_WHATSAPP: string;
  // Add other env variables here
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
