import type { Metadata } from "next";

import { AppShell } from "@/components/shell/AppShell";
import "./globals.css";

export const metadata: Metadata = {
  title: "W2Health Intelligence · Works2Data",
  description:
    "Decision Intelligence Platform for Healthcare — produto W2Health Intelligence da Works2Data. " +
    "Ambiente demonstrativo com dados sintéticos.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
