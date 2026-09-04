import { ReactNode, Suspense } from "react";

import { DemoBanner } from "@/components/shell/DemoBanner";
import { Header } from "@/components/shell/Header";
import { Sidebar } from "@/components/shell/Sidebar";
import { FiltersProvider } from "@/lib/filters";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <Suspense fallback={<div className="p-6 text-sm text-slate-400">Carregando…</div>}>
      <FiltersProvider>
        <div className="flex min-h-screen flex-col">
          <DemoBanner />
          <div className="flex flex-1">
            <Sidebar />
            <div className="flex min-w-0 flex-1 flex-col">
              <Header />
              <main className="flex-1 p-6">{children}</main>
              <footer className="border-t border-slate-200 px-6 py-3 text-center text-[11px] text-slate-400">
                W2Health Intelligence — um produto <span className="font-medium text-slate-500">Works2Data</span> ·
                Ambiente demonstrativo com dados sintéticos · Nenhum dado de pessoa real é utilizado.
              </footer>
            </div>
          </div>
        </div>
      </FiltersProvider>
    </Suspense>
  );
}
