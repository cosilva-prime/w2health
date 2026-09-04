"use client";

import { Card, DataState, Stat } from "@/components/ui";
import { filtersQuery, useFilters } from "@/lib/filters";
import { fmtBRL, fmtBRLCompact, fmtPct, fmtPP } from "@/lib/format";
import { useApi } from "@/lib/useApi";

interface Bloco {
  despesa_bruta: number;
  glosas: number;
  coparticipacao: number;
  despesa_liquida: number;
  receita: number;
  sinistralidade_bruta: number;
  sinistralidade_liquida: number;
}
interface Decomposicao {
  variacao_pp: number;
  efeito_bruta_pp: number;
  efeito_glosa_pp: number;
  efeito_coparticipacao_pp: number;
  efeito_receita_pp: number;
}
interface Composicao {
  atual: Bloco;
  comparacao_valores: Bloco | null;
  decomposicao: Decomposicao | null;
}

function Barra({ label, valor, max, cor }: { label: string; valor: number; max: number; cor: string }) {
  const pct = max > 0 ? Math.min(100, (Math.abs(valor) / max) * 100) : 0;
  return (
    <div>
      <div className="flex items-baseline justify-between text-xs">
        <span className="text-slate-500">{label}</span>
        <span className="font-medium tabular-nums text-slate-700">{fmtBRLCompact(valor)}</span>
      </div>
      <div className="mt-0.5 h-2.5 w-full rounded-full bg-slate-100">
        <div className={`h-2.5 rounded-full ${cor}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export function CompositionCard() {
  const f = useFilters();
  const ready = f.competencia != null;
  const { data, isLoading, error } = useApi<Composicao>(
    ready ? `/analytics/sinistralidade/composicao${filtersQuery(f)}` : null,
  );

  const a = data?.atual;
  const max = a ? a.despesa_bruta : 0;

  return (
    <Card title="Composição da despesa assistencial">
      <DataState isLoading={isLoading && !data} error={error} empty={!a}>
        {a && (
          <>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Stat label="Sinistralidade bruta" value={fmtPct(a.sinistralidade_bruta)} hint="despesa bruta / receita" />
              <Stat label="Sinistralidade líquida" value={fmtPct(a.sinistralidade_liquida)} hint="oficial do MVP" />
              <Stat label="Receita" value={fmtBRLCompact(a.receita)} />
              <Stat label="Despesa líquida" value={fmtBRLCompact(a.despesa_liquida)} />
            </div>

            <div className="mt-4 space-y-3">
              <Barra label="Despesa bruta (apresentado)" valor={a.despesa_bruta} max={max} cor="bg-slate-400" />
              <Barra label="(−) Glosas" valor={-a.glosas} max={max} cor="bg-rose-400" />
              <Barra label="(−) Coparticipação" valor={-a.coparticipacao} max={max} cor="bg-amber-400" />
              <Barra label="= Despesa líquida assistencial" valor={a.despesa_liquida} max={max} cor="bg-brand-600" />
            </div>

            {data?.decomposicao && (
              <div className="mt-4 border-t border-slate-100 pt-3">
                <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-400">
                  Por que a sinistralidade líquida variou {fmtPP(data.decomposicao.variacao_pp)}?
                </p>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                  <MiniEfeito label="Despesa bruta" valor={data.decomposicao.efeito_bruta_pp} />
                  <MiniEfeito label="Glosas" valor={data.decomposicao.efeito_glosa_pp} />
                  <MiniEfeito label="Coparticipação" valor={data.decomposicao.efeito_coparticipacao_pp} />
                  <MiniEfeito label="Receita" valor={data.decomposicao.efeito_receita_pp} />
                </div>
                <p className="mt-2 text-[11px] text-slate-400">
                  Identidade exata: a soma dos 4 efeitos reconcilia com a variação observada.
                </p>
              </div>
            )}
            <p className="mt-3 text-[11px] text-slate-400">
              Convenção do MVP: o KPI principal ({" "}<b>Sinistralidade</b>{" "}) usa a base{" "}
              <b>líquida</b> (bruta − glosas − coparticipação). A base bruta é sempre exibida
              ao lado para evitar ambiguidade — {fmtBRL(a.despesa_bruta)} vs{" "}
              {fmtBRL(a.despesa_liquida)}.
            </p>
          </>
        )}
      </DataState>
    </Card>
  );
}

function MiniEfeito({ label, valor }: { label: string; valor: number }) {
  const cor = valor > 0.05 ? "text-rose-600" : valor < -0.05 ? "text-emerald-600" : "text-slate-400";
  return (
    <div className="rounded-lg border border-slate-200 p-2 text-center">
      <div className="text-[11px] text-slate-400">{label}</div>
      <div className={`text-sm font-semibold tabular-nums ${cor}`}>{fmtPP(valor)}</div>
    </div>
  );
}
