"use client";

import Link from "next/link";
import { useState } from "react";

import { Card, DataState, EfeitoBadge } from "@/components/ui";
import { filtersQuery, useFilters } from "@/lib/filters";
import { fmtBRLCompact, fmtNum } from "@/lib/format";
import { useApi } from "@/lib/useApi";

interface RankItem {
  id_prestador: number;
  nome: string;
  tipo: string;
  especialidade_principal: string;
  impacto: number;
  despesa_atual: number;
  eventos_atual: number;
  custo_medio_atual: number;
  participacao_variacao: number;
  bridge: { efeito_principal: string };
}
interface ListItem {
  id_prestador: number;
  nome: string;
  tipo: string;
  regiao: string;
  especialidade_principal: string;
  despesa: number;
  eventos: number;
  beneficiarios: number;
  custo_medio: number;
  participacao: number;
}
interface Anomalia {
  id_prestador: number;
  nome: string;
  especialidade_principal: string;
  custo_medio: number;
  metricas_fora_padrao: string[];
  severidade: string;
}

export default function PrestadoresPage() {
  const f = useFilters();
  const [direcao, setDirecao] = useState<"alta" | "baixa">("alta");
  const ready = f.competencia != null;

  const rank = useApi<{ itens: RankItem[] }>(
    ready ? `/analytics/prestadores/ranking-variacao${filtersQuery(f, { direcao, limit: "10" })}` : null,
  );
  const lista = useApi<{ itens: ListItem[]; total: number }>(
    ready ? `/analytics/prestadores${filtersQuery(f, { page_size: "30", sort: "despesa" })}` : null,
  );
  const anom = useApi<{ itens: Anomalia[] }>(
    ready ? `/analytics/prestadores/anomalias${filtersQuery(f)}` : null,
  );
  const flagged = new Set((anom.data?.itens ?? []).map((a) => a.id_prestador));

  return (
    <div className="space-y-5">
      <Card
        title="Prestadores que mais contribuíram para a variação da despesa"
        action={
          <div className="flex gap-1 text-xs">
            {(["alta", "baixa"] as const).map((d) => (
              <button
                key={d}
                onClick={() => setDirecao(d)}
                className={`rounded-md px-2 py-1 ${direcao === d ? "bg-brand-600 text-white" : "bg-slate-100 text-slate-600"}`}
              >
                {d === "alta" ? "Maior aumento" : "Maior redução"}
              </button>
            ))}
          </div>
        }
      >
        <DataState isLoading={rank.isLoading && !rank.data} error={rank.error} empty={!rank.data?.itens?.length}>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 text-left text-xs uppercase text-slate-400">
                <th className="py-2">#</th>
                <th className="py-2">Prestador</th>
                <th className="py-2 text-right">Impacto</th>
                <th className="py-2 text-right">% variação</th>
                <th className="py-2 text-right">Efeito</th>
              </tr>
            </thead>
            <tbody>
              {(rank.data?.itens ?? []).map((r, i) => (
                <tr key={r.id_prestador} className="border-b border-slate-50">
                  <td className="py-2 text-slate-400">{i + 1}</td>
                  <td className="py-2">
                    <Link href={`/prestadores/${r.id_prestador}${filtersQuery(f)}`} className="text-brand-600 hover:underline">
                      {r.nome}
                    </Link>
                    {flagged.has(r.id_prestador) && <span className="ml-1" title="Fora do padrão">🚩</span>}
                    <div className="text-xs text-slate-400">{r.especialidade_principal}</div>
                  </td>
                  <td className="py-2 text-right font-medium tabular-nums">{fmtBRLCompact(r.impacto)}</td>
                  <td className="py-2 text-right tabular-nums">{r.participacao_variacao.toFixed(0)}%</td>
                  <td className="py-2 text-right"><EfeitoBadge efeito={r.bridge.efeito_principal} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </DataState>
      </Card>

      {(anom.data?.itens?.length ?? 0) > 0 && (
        <Card title="Comportamento fora do padrão (z-score vs pares)">
          <div className="grid gap-2 sm:grid-cols-2">
            {anom.data!.itens.slice(0, 6).map((a) => (
              <Link
                key={a.id_prestador}
                href={`/prestadores/${a.id_prestador}${filtersQuery(f)}`}
                className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm hover:bg-amber-100"
              >
                <div className="font-medium text-amber-900">🚩 {a.nome}</div>
                <div className="text-xs text-amber-800">
                  {a.especialidade_principal} · custo médio {fmtBRLCompact(a.custo_medio)} · fora do padrão em:{" "}
                  {a.metricas_fora_padrao.join(", ")}
                </div>
              </Link>
            ))}
          </div>
        </Card>
      )}

      <Card title={`Todos os prestadores no mês (${lista.data?.total ?? 0})`}>
        <DataState isLoading={lista.isLoading && !lista.data} error={lista.error}>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-sm">
              <thead>
                <tr className="border-b border-slate-100 text-left text-xs uppercase text-slate-400">
                  <th className="py-2">Prestador</th>
                  <th className="py-2">Tipo</th>
                  <th className="py-2 text-right">Custo total</th>
                  <th className="py-2 text-right">Eventos</th>
                  <th className="py-2 text-right">Benef.</th>
                  <th className="py-2 text-right">Custo médio</th>
                  <th className="py-2 text-right">Part.</th>
                </tr>
              </thead>
              <tbody>
                {(lista.data?.itens ?? []).map((r) => (
                  <tr key={r.id_prestador} className="border-b border-slate-50">
                    <td className="py-2">
                      <Link href={`/prestadores/${r.id_prestador}${filtersQuery(f)}`} className="text-brand-600 hover:underline">
                        {r.nome}
                      </Link>
                      {flagged.has(r.id_prestador) && <span className="ml-1">🚩</span>}
                    </td>
                    <td className="py-2 capitalize text-slate-500">{r.tipo.replace("_", " ")}</td>
                    <td className="py-2 text-right tabular-nums">{fmtBRLCompact(r.despesa)}</td>
                    <td className="py-2 text-right tabular-nums">{fmtNum(r.eventos)}</td>
                    <td className="py-2 text-right tabular-nums">{fmtNum(r.beneficiarios)}</td>
                    <td className="py-2 text-right tabular-nums">{fmtBRLCompact(r.custo_medio)}</td>
                    <td className="py-2 text-right tabular-nums">{(r.participacao * 100).toFixed(1)}%</td>
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
