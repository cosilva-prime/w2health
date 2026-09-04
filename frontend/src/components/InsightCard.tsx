"use client";

import Link from "next/link";
import { useState } from "react";

import { type Insight, insightHref } from "@/lib/api";
import { corSeveridade } from "@/lib/format";

export function InsightChip({ insight }: { insight: Insight }) {
  return (
    <Link
      href={insightHref(insight)}
      className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-sm transition hover:brightness-[0.98] ${corSeveridade(
        insight.severidade,
      )}`}
    >
      <span aria-hidden>{insight.emoji}</span>
      <span className="font-medium">{insight.titulo}</span>
    </Link>
  );
}

export function InsightCard({ insight }: { insight: Insight }) {
  const [open, setOpen] = useState(false);
  return (
    <article className={`rounded-xl border p-4 ${corSeveridade(insight.severidade)}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="flex items-center gap-2 text-sm font-semibold">
            <span aria-hidden>{insight.emoji}</span>
            {insight.titulo}
          </h3>
          <p className="mt-1 text-sm opacity-90">{insight.descricao}</p>
        </div>
        <Link
          href={insightHref(insight)}
          className="shrink-0 rounded-md bg-white/70 px-2.5 py-1 text-xs font-medium hover:bg-white"
        >
          Investigar →
        </Link>
      </div>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="mt-2 text-xs font-medium underline decoration-dotted underline-offset-2 opacity-80"
      >
        {open ? "Ocultar" : "Como calculamos"}
      </button>
      {open && (
        <div className="mt-2 space-y-2 rounded-lg bg-white/60 p-3 text-xs">
          <p className="font-mono text-slate-600">{insight.metodologia}</p>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-1">
            {Object.entries(insight.metricas).map(([k, v]) => (
              <div key={k} className="flex justify-between gap-2">
                <dt className="text-slate-500">{k}</dt>
                <dd className="font-medium text-slate-800">
                  {typeof v === "number" ? v.toLocaleString("pt-BR") : JSON.stringify(v)}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      )}
    </article>
  );
}
