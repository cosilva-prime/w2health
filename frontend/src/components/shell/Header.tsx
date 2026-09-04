"use client";

import { usePathname } from "next/navigation";

import { Breadcrumbs } from "@/components/shell/Breadcrumbs";
import { fmtCompetencia, LABEL_COMPARACAO } from "@/lib/format";
import { useFilters } from "@/lib/filters";
import { NAV_ITEMS } from "@/lib/nav";

function currentTitle(pathname: string): string {
  const match = NAV_ITEMS.find((item) => pathname === item.href || pathname.startsWith(`${item.href}/`));
  return match?.label ?? "W2Health Intelligence";
}

export function Header() {
  const pathname = usePathname();
  const f = useFilters();

  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="flex flex-wrap items-center justify-between gap-3 px-6 py-3">
        <div>
          <Breadcrumbs />
          <h1 className="text-lg font-semibold text-slate-900">{currentTitle(pathname)}</h1>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-1.5 text-xs text-slate-500">
            Competência
            <select
              className="rounded-md border border-slate-300 bg-white px-2 py-1 text-xs text-slate-700"
              value={f.competencia ?? ""}
              onChange={(e) => f.setCompetencia(e.target.value)}
            >
              {f.competencias.map((c) => (
                <option key={c} value={c}>
                  {fmtCompetencia(`${c}-01`)}
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-1.5 text-xs text-slate-500">
            Comparar com
            <select
              className="rounded-md border border-slate-300 bg-white px-2 py-1 text-xs text-slate-700"
              value={f.comparacao}
              onChange={(e) => f.setComparacao(e.target.value)}
            >
              {Object.entries(LABEL_COMPARACAO).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </label>
          <span className="rounded-full bg-gold-50 px-3 py-1 text-xs font-medium text-gold-700 ring-1 ring-gold-400">
            demo
          </span>
        </div>
      </div>
    </header>
  );
}
