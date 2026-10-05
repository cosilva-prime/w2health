"use client";

import Link from "next/link";

import { Card, DataState } from "@/components/ui";
import type { ConcentracaoVariacao } from "@/lib/api";
import { filtersQuery, useFilters } from "@/lib/filters";
import { fmtBRLCompact, fmtPct } from "@/lib/format";
import { useApi } from "@/lib/useApi";

/** C1 (v1.2) — mostra, no TOPO da explicação, quantos beneficiários concentram o
 *  aumento de despesa líquida do período. Sem drill. */
export function ConcentracaoBeneficiariosCard() {
  const f = useFilters();
  const { data, error, isLoading } = useApi<ConcentracaoVariacao>(
    `/analytics/sinistralidade/concentracao-variacao${filtersQuery(f, {}, { withContrato: true })}`,
  );

  const semAumento = data && data.delta_positivo_total <= 0;

  return (
    <Card title="Onde investigar primeiro — beneficiários">
      <DataState isLoading={isLoading} error={error} empty={!data}>
        {data && (
          <div className="space-y-3 text-sm">
            {semAumento ? (
              <p className="text-slate-500">
                Sem aumento líquido de despesa por beneficiário neste período.
              </p>
            ) : (
              <>
                <p className="text-slate-700">
                  O aumento de despesa líquida somou{" "}
                  <strong>{fmtBRLCompact(data.delta_positivo_total)}</strong>.{" "}
                  <strong>{data.n_para_credito_50pct}</strong> beneficiário(s) concentram metade dele;
                  os 5 maiores respondem por{" "}
                  <strong>{fmtPct(data.top5_share_do_aumento * 100)}</strong>{" "}
                  (Gini {data.gini_do_aumento.toFixed(2)}).
                </p>
                <ul className="divide-y divide-slate-50">
                  {data.top.slice(0, 5).map((b) => (
                    <li key={b.id} className="flex items-center justify-between py-1.5">
                      <Link
                        href={`/beneficiarios/${b.id}`}
                        className="font-medium text-brand-700 hover:underline"
                      >
                        {b.codigo}
                      </Link>
                      <span className="tabular-nums text-slate-600">
                        +{fmtBRLCompact(b.delta)}{" "}
                        <span className="text-slate-400">({fmtPct(b.participacao_pct)})</span>
                      </span>
                    </li>
                  ))}
                </ul>
                <Link
                  href={`/beneficiarios${filtersQuery(f)}`}
                  className="inline-block text-xs font-medium text-brand-600 hover:underline"
                >
                  Investigar beneficiários →
                </Link>
              </>
            )}
          </div>
        )}
      </DataState>
    </Card>
  );
}
