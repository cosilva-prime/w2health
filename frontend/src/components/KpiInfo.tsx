"use client";

/**
 * Transparência de indicador — botão "ⓘ" que abre definição, fórmula, composição,
 * competência, filtros aplicados, última atualização e origem lógica.
 *
 * Tudo vem de `GET /api/meta/transparencia` (definições implementadas no motor + procedência
 * real do banco). Se algo não existir, mostramos "Não disponível" — nunca fabricamos origem.
 * Dado sintético é sempre sinalizado.
 */

import { useState } from "react";

import { Dialog, StatusBadge } from "@/components/ui";
import { useFilters } from "@/lib/filters";
import { fmtCompetencia, LABEL_COMPARACAO } from "@/lib/format";
import { useApi } from "@/lib/useApi";

interface KpiDef {
  rotulo: string;
  definicao: string;
  formula: string;
  composicao: string[];
  unidade: string;
  origem: string;
}

export interface Transparencia {
  dados_sinteticos: boolean;
  ultima_atualizacao: string | null;
  tipo_carga: string | null;
  janela: { inicio: string; fim: string } | null;
  camada: string;
  kpis: Record<string, KpiDef>;
}

const NA = <span className="text-slate-400">Não disponível</span>;

function fmtDataHora(iso: string | null): React.ReactNode {
  if (!iso) return NA;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? NA : d.toLocaleString("pt-BR");
}

export function KpiInfo({ kpi, extraFiltros }: { kpi: string; extraFiltros?: string[] }) {
  const [open, setOpen] = useState(false);
  const f = useFilters();
  const { data, error } = useApi<Transparencia>(open ? "/meta/transparencia" : null);
  const def = data?.kpis[kpi];

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Como este indicador é calculado"
        title="Como este indicador é calculado"
        className="rounded-full text-xs leading-none text-slate-300 hover:text-brand-600"
      >
        ⓘ
      </button>
      <Dialog open={open} onClose={() => setOpen(false)} title={def?.rotulo ?? "Transparência do indicador"} wide>
        {error && <p className="text-rose-600">Não foi possível carregar a definição.</p>}
        {!data && !error && <p className="text-slate-400">Carregando…</p>}
        {data && !def && <p>{NA}</p>}
        {data && def && (
          <dl className="grid grid-cols-[9rem_1fr] gap-x-4 gap-y-2 text-sm">
            <dt className="text-slate-400">Definição</dt>
            <dd>{def.definicao}</dd>
            <dt className="text-slate-400">Fórmula</dt>
            <dd className="font-mono text-xs">{def.formula}</dd>
            {def.composicao.length > 0 && (
              <>
                <dt className="text-slate-400">Composição</dt>
                <dd>
                  <ol className="space-y-0.5 font-mono text-xs">
                    {def.composicao.map((l) => (
                      <li key={l}>{l}</li>
                    ))}
                  </ol>
                </dd>
              </>
            )}
            <dt className="text-slate-400">Competência</dt>
            <dd>{f.competencia ? fmtCompetencia(`${f.competencia}-01`) : NA}</dd>
            <dt className="text-slate-400">Filtros aplicados</dt>
            <dd>
              Comparação: {LABEL_COMPARACAO[f.comparacao] ?? f.comparacao}
              {f.contratoId ? ` · Contrato #${f.contratoId}` : ""}
              {(extraFiltros ?? []).map((x) => ` · ${x}`)}
            </dd>
            <dt className="text-slate-400">Última atualização</dt>
            <dd>{fmtDataHora(data.ultima_atualizacao)}</dd>
            <dt className="text-slate-400">Origem lógica</dt>
            <dd>{def.origem}</dd>
            <dt className="text-slate-400">Camada</dt>
            <dd>{data.camada}</dd>
            <dt className="text-slate-400">Natureza do dado</dt>
            <dd>
              {data.dados_sinteticos ? (
                <StatusBadge tone="gold">Dados sintéticos (demonstração)</StatusBadge>
              ) : data.tipo_carga ? (
                <StatusBadge tone="info">Carga do cliente</StatusBadge>
              ) : (
                NA
              )}
            </dd>
          </dl>
        )}
      </Dialog>
    </>
  );
}
