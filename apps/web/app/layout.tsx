import "./globals.css";

import type { Metadata } from "next";
import type { ReactNode } from "react";

import { Providers } from "@/src/providers/Providers";

export const metadata: Metadata = {
  title: "AtendeCRM SaaS",
  description: "Plataforma SaaS multiempresa e multiloja para atendimento WhatsApp oficial."
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="pt-BR">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
