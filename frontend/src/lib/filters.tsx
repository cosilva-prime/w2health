"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { createContext, useCallback, useContext, useMemo } from "react";

import { useApi } from "@/lib/useApi";

export interface GlobalFilters {
  competencia: string | null; // AAAA-MM (null = última disponível)
  comparacao: string;
  competencias: string[]; // ISO date list
  setCompetencia: (v: string) => void;
  setComparacao: (v: string) => void;
}

const Ctx = createContext<GlobalFilters | null>(null);

export function FiltersProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  const { data } = useApi<{ itens: string[]; ultima: string | null }>("/meta/competencias");
  const competencias = useMemo(
    () => (data?.itens ?? []).map((c) => c.slice(0, 7)),
    [data],
  );
  const ultima = data?.ultima ? data.ultima.slice(0, 7) : null;

  const competencia = params.get("competencia") ?? ultima;
  const comparacao = params.get("comparacao") ?? "mes_anterior";

  const push = useCallback(
    (patch: Record<string, string>) => {
      const next = new URLSearchParams(params.toString());
      for (const [k, v] of Object.entries(patch)) next.set(k, v);
      router.replace(`${pathname}?${next.toString()}`, { scroll: false });
    },
    [params, pathname, router],
  );

  const value = useMemo<GlobalFilters>(
    () => ({
      competencia,
      comparacao,
      competencias,
      setCompetencia: (v) => push({ competencia: v }),
      setComparacao: (v) => push({ comparacao: v }),
    }),
    [competencia, comparacao, competencias, push],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useFilters(): GlobalFilters {
  const c = useContext(Ctx);
  if (!c) throw new Error("useFilters fora do FiltersProvider");
  return c;
}

/** Querystring padrão para os endpoints, a partir dos filtros globais. */
export function filtersQuery(f: GlobalFilters, extra: Record<string, string> = {}): string {
  const p = new URLSearchParams();
  if (f.competencia) p.set("competencia", f.competencia);
  p.set("comparacao", f.comparacao);
  for (const [k, v] of Object.entries(extra)) p.set(k, v);
  return `?${p.toString()}`;
}
