"use client";

import Link from "next/link";

import { DataState } from "@/components/ui";
import { filtersQuery, useFilters } from "@/lib/filters";
import { corEvidencia, fmtBRLCompact, LABEL_CONFIANCA, LABEL_EVIDENCIA } from "@/lib/format";
import { useApi } from "@/lib/useApi";

interface Evidencia {
  tipo_evidencia: string;
  nivel_confianca: string;
  texto: string;
}
interface CoorteBucket {
  codigo: string;
  rotulo: string;
  n_beneficiarios: number;
  despesa_anterior: number;
  despesa_atual: number;
  delta: number;
  participacao_variacao: number;
  evidencias: Evidencia[];
  beneficiarios_amostra: { id: number; codigo: string; valor: number }[];
}
interface Causas {
  despesa_anterior: number;
  despesa_atual: number;
  delta_total: number;
  coortes: CoorteBucket[];
  reconciliacao: { soma_coortes: number; delta_observado: number; ok: boolean };
  metodologia: string;
}

function EvidenciaBadge({ ev }: { ev: Evidencia }) {
  return (
    <div className={`rounded-md border px-2 py-1 text-xs ${corEvidencia(ev.tipo_evidencia)}`}>
      <span className="font-semibold">{LABEL_EVIDENCIA[ev.tipo_evidencia] ?? ev.tipo_evidencia}</span>
      <span className="opacity-70"> · {LABEL_CONFIANCA[ev.nivel_confianca] ?? ev.nivel_confianca}</span>
      <p className="mt-0.5 font-normal">{ev.texto}</p>
    </div>
  );
}

export function CausasPanel({ dimensao, chave, categoria }: { dimensao: string; chave: string; categoria: string }) {
  const f = useFilters();
  const ready = f.competencia != null;
  const { data, isLoading, error } = useApi<Causas>(
    ready ? `/analytics/sinistralidade/explain/${dimensao}/${chave}/causas${filtersQuery(f)}` : null,
  );

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <h3 className="text-sm font-semibold text-slate-900">
        Por que {categoria} {data && data.delta_total < 0 ? "caiu" : "aumentou"}?
      </h3>
      <p className="mb-3 text-xs text-slate-500">
        Coortes de beneficiários — cada achado é rotulado como Fato, Hipótese ou A investigar.
        Nunca afirmamos causalidade sem evidência nos dados.
      </p>
      <DataState isLoading={isLoading && !data} error={error} empty={!data?.coortes?.length}>
        {data && (
          <>
            <div className="space-y-3">
              {data.coortes
                .slice()
                .sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta))
                .map((c) => {
                  const reduziu = c.delta < 0;
                  return (
                    <div key={c.codigo} className="rounded-lg border border-slate-200 p-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <span
                          className={`inline-block h-2 w-2 shrink-0 rounded-full ${reduziu ? "bg-emerald-500" : "bg-rose-500"}`}
                          title={reduziu ? "ajudou a reduzir a despesa" : "empurrou a despesa para cima"}
                        />
                        <span className="font-medium text-slate-800">{c.rotulo}</span>
                        <span className="text-xs text-slate-400">{c.n_beneficiarios} beneficiário(s)</span>
                        <span className="ml-auto tabular-nums text-sm font-medium text-slate-700">
                          {fmtBRLCompact(c.delta)}
                        </span>
                        <span className="tabular-nums text-xs text-slate-400">
                          {Math.abs(c.participacao_variacao).toFixed(0)}% da variação
                        </span>
                      </div>
                      <div className="mt-2 grid gap-1.5 sm:grid-cols-2">
                        {c.evidencias.map((ev, i) => (
                          <EvidenciaBadge key={i} ev={ev} />
                        ))}
                      </div>
                      {c.beneficiarios_amostra.length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          {c.beneficiarios_amostra.slice(0, 5).map((b) => (
                            <Link
                              key={b.id}
                              href={`/beneficiarios/${b.id}`}
                              className="rounded border border-slate-200 px-1.5 py-0.5 font-mono text-[11px] text-brand-600 hover:bg-brand-50"
                            >
                              {b.codigo}
                            </Link>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
            </div>
            <p className="mt-3 text-[11px] text-slate-400">
              Reconciliação: soma das coortes = {fmtBRLCompact(data.reconciliacao.soma_coortes)} · variação
              observada = {fmtBRLCompact(data.reconciliacao.delta_observado)}{" "}
              {data.reconciliacao.ok ? "✓" : "⚠"}
            </p>
          </>
        )}
      </DataState>
    </section>
  );
}
