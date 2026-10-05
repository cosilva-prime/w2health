"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { Card, DataState } from "@/components/ui";
import type { ContratosLista } from "@/lib/api";
import { filtersQuery, useFilters } from "@/lib/filters";
import { fmtBRLCompact, fmtNum, fmtPct, fmtSignedPct } from "@/lib/format";
import { useApi } from "@/lib/useApi";

type SortKey = "despesa_liquida" | "top5_share" | "vidas" | "variacao_despesa_liquida_pct";

export default function ContratosPage() {
  const f = useFilters();
  const [sort, setSort] = useState<SortKey>("despesa_liquida");
  const { data, error, isLoading } = useApi<ContratosLista>(
    `/analytics/contratos${filtersQuery(f)}`,
  );

  const itens = useMemo(() => {
    const rows = [...(data?.itens ?? [])];
    rows.sort((a, b) => (b[sort] ?? -Infinity) - (a[sort] ?? -Infinity));
    return rows;
  }, [data, sort]);

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-lg font-semibold text-slate-900">Contract Intelligence</h1>
        <p className="text-sm text-slate-500">
          Vidas, despesa (bruta → glosas → coparticipação → líquida) e concentração por contrato.
        </p>
      </header>

      {data?.aviso && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-800">
          ⚠️ {data.aviso}
        </div>
      )}

      <Card
        title={`${data?.total ?? 0} contratos`}
        action={
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value as SortKey)}
            className="rounded-md border border-slate-200 px-2 py-1 text-xs text-slate-600"
          >
            <option value="despesa_liquida">ordenar por despesa líquida</option>
            <option value="top5_share">ordenar por concentração</option>
            <option value="variacao_despesa_liquida_pct">ordenar por variação</option>
            <option value="vidas">ordenar por vidas</option>
          </select>
        }
      >
        <DataState isLoading={isLoading} error={error} empty={!itens.length}>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 text-left text-xs uppercase text-slate-400">
                  <th className="py-2 pr-3">Contrato</th>
                  <th className="px-3">Vidas</th>
                  <th className="px-3 text-right">Despesa líquida</th>
                  <th className="px-3 text-right">Δ vs comp.</th>
                  <th className="px-3 text-right">PMPM</th>
                  <th className="px-3 text-right">Conc. (top-5)</th>
                  <th className="px-3 text-right">Alto custo</th>
                </tr>
              </thead>
              <tbody>
                {itens.map((c) => (
                  <tr key={c.id_contrato} className="border-b border-slate-50 hover:bg-slate-50">
                    <td className="py-2 pr-3">
                      <Link
                        href={`/contratos/${c.id_contrato}${filtersQuery(f)}`}
                        className="font-medium text-brand-700 hover:underline"
                      >
                        {c.nome}
                      </Link>
                      <div className="text-xs text-slate-400">
                        {c.plano} · {c.tipo}
                      </div>
                    </td>
                    <td className="px-3">{fmtNum(c.vidas)}</td>
                    <td className="px-3 text-right">{fmtBRLCompact(c.despesa_liquida)}</td>
                    <td
                      className={`px-3 text-right ${
                        (c.variacao_despesa_liquida_pct ?? 0) > 0 ? "text-rose-600" : "text-emerald-600"
                      }`}
                    >
                      {fmtSignedPct(c.variacao_despesa_liquida_pct)}
                    </td>
                    <td className="px-3 text-right">{fmtBRLCompact(c.custo_pmpm)}</td>
                    <td className="px-3 text-right">{fmtPct(c.top5_share * 100)}</td>
                    <td className="px-3 text-right">{c.n_beneficiarios_alto_custo || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </DataState>
      </Card>
    </div>
  );
}
