"use client";

import Link from "next/link";
import { useState } from "react";

import { InsightCard } from "@/components/InsightCard";
import { Card, DataState } from "@/components/ui";
import type { Insight } from "@/lib/api";
import { filtersQuery, useFilters } from "@/lib/filters";
import { corSeveridade, fmtNum } from "@/lib/format";
import { useApi } from "@/lib/useApi";

const SEVERIDADES = [
  ["", "Todas"],
  ["alta", "🔴 Alta"],
  ["media", "🟠 Média"],
  ["positiva", "🟢 Positiva"],
  ["info", "🔵 Informativo"],
];

interface Alerta {
  regra_id: number;
  regra_nome: string;
  entidade: string;
  entidade_id: string;
  rotulo: string;
  indicador_rotulo: string;
  unidade: string;
  valor_observado: number;
  operador: string;
  limite: number;
  severidade: string;
  deep_link: { rota: string; params: Record<string, string> };
}

const SEV_ALERTA_MAP: Record<string, string> = { critica: "alta", atencao: "media", informativo: "info" };
const SEV_ALERTA_LABEL: Record<string, string> = { critica: "CRÍTICO", atencao: "ATENÇÃO", informativo: "INFO" };

function alertaHref(a: Alerta): string {
  const p = new URLSearchParams(a.deep_link.params);
  const s = p.toString();
  return `${a.deep_link.rota}${s ? `?${s}` : ""}`;
}

function AlertaCard({ a }: { a: Alerta }) {
  return (
    <article className={`rounded-xl border p-4 ${corSeveridade(SEV_ALERTA_MAP[a.severidade] ?? "info")}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-xs font-bold uppercase tracking-wide opacity-80">
            {SEV_ALERTA_LABEL[a.severidade] ?? a.severidade}
          </div>
          <h3 className="text-sm font-semibold">{a.rotulo}</h3>
          <p className="mt-1 text-sm opacity-90">
            {a.regra_nome} — {a.indicador_rotulo}:{" "}
            <b>{fmtNum(a.valor_observado)}{a.unidade === "%" ? "%" : a.unidade === "R$" ? "" : ` ${a.unidade}`}</b>{" "}
            (limite configurado: {a.operador} {fmtNum(a.limite)}{a.unidade === "%" ? "%" : ""})
          </p>
        </div>
        <Link href={alertaHref(a)} className="shrink-0 rounded-md bg-white/70 px-2.5 py-1 text-xs font-medium hover:bg-white">
          Investigar →
        </Link>
      </div>
    </article>
  );
}

export default function InsightsPage() {
  const f = useFilters();
  const [aba, setAba] = useState<"insights" | "alertas">("insights");
  const [sev, setSev] = useState("");
  const ready = f.competencia != null;
  const extra: Record<string, string> = sev ? { severidade: sev } : {};
  const insights = useApi<{ itens: Insight[]; total: number }>(
    ready && aba === "insights" ? `/analytics/insights${filtersQuery(f, extra)}` : null,
  );
  const alertas = useApi<{ itens: Alerta[]; total: number }>(
    ready && aba === "alertas" ? `/analytics/alertas${filtersQuery(f)}` : null,
  );

  return (
    <div className="space-y-4">
      <div className="flex gap-1 border-b border-slate-200">
        {(
          [
            ["insights", `💡 Insights automáticos${insights.data ? ` (${insights.data.total})` : ""}`],
            ["alertas", `🔔 Alertas configurados${alertas.data ? ` (${alertas.data.total})` : ""}`],
          ] as const
        ).map(([k, label]) => (
          <button
            key={k}
            onClick={() => setAba(k)}
            className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium ${
              aba === k ? "border-brand-600 text-brand-700" : "border-transparent text-slate-400 hover:text-slate-600"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {aba === "insights" && (
        <>
          <Card
            title="Insights automáticos"
            action={
              <select
                className="rounded-md border border-slate-300 px-2 py-1 text-xs"
                value={sev}
                onChange={(e) => setSev(e.target.value)}
              >
                {SEVERIDADES.map(([v, l]) => (
                  <option key={v} value={v}>{l}</option>
                ))}
              </select>
            }
          >
            <p className="text-xs text-slate-500">
              Descoberta automática do motor — nenhuma configuração do usuário. Todos os valores
              são <b>calculados a partir dos dados</b>; se o banco muda, os insights mudam. Cada
              card mostra a fórmula em &ldquo;Como calculamos&rdquo;.
            </p>
          </Card>
          <DataState isLoading={insights.isLoading && !insights.data} error={insights.error} empty={!insights.data?.itens?.length}>
            <div className="space-y-3">
              {(insights.data?.itens ?? []).map((i) => (
                <InsightCard key={i.id} insight={i} />
              ))}
            </div>
          </DataState>
        </>
      )}

      {aba === "alertas" && (
        <>
          <Card
            title="Alertas configurados"
            action={
              <Link href="/configuracao/insights" className="text-xs font-medium text-brand-600 hover:underline">
                Configurar regras →
              </Link>
            }
          >
            <p className="text-xs text-slate-500">
              Regra definida pelo gestor em <b>Configuração</b> — só aparece aqui quando o
              indicador realmente cruza o limite configurado no período. Diferente do insight:
              o alerta não existe até você criar a regra.
            </p>
          </Card>
          <DataState isLoading={alertas.isLoading && !alertas.data} error={alertas.error} empty={!alertas.data?.itens?.length}>
            <div className="space-y-3">
              {(alertas.data?.itens ?? []).map((a, i) => (
                <AlertaCard key={`${a.regra_id}-${a.entidade_id}-${i}`} a={a} />
              ))}
            </div>
          </DataState>
        </>
      )}
    </div>
  );
}
