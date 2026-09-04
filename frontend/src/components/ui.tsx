"use client";

import Link from "next/link";
import { ReactNode } from "react";

import { fmtPP, fmtSignedPct } from "@/lib/format";

export function Card({
  children,
  className = "",
  title,
  action,
}: {
  children: ReactNode;
  className?: string;
  title?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <section className={`rounded-xl border border-slate-200 bg-white shadow-sm ${className}`}>
      {(title || action) && (
        <header className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
          <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
          {action}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

export function Stat({
  label,
  value,
  delta,
  deltaKind = "pp",
  hint,
  invertColors = false,
  href,
}: {
  label: string;
  value: ReactNode;
  delta?: number | null;
  deltaKind?: "pp" | "pct";
  hint?: string;
  invertColors?: boolean;
  href?: string;
}) {
  const good = delta == null ? null : invertColors ? delta > 0 : delta < 0;
  const color =
    good == null ? "text-slate-400" : good ? "text-emerald-600" : "text-rose-600";
  return (
    <div className={`rounded-xl border border-slate-200 bg-white p-4 shadow-sm ${href ? "transition hover:border-brand-300 hover:shadow" : ""}`}>
      <div className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-slate-900">
        {href ? (
          <Link href={href} className="hover:text-brand-700">
            {value} <span className="text-sm font-normal text-brand-400">↗</span>
          </Link>
        ) : (
          value
        )}
      </div>
      {delta != null && (
        <div className={`mt-1 text-xs font-medium ${color}`}>
          {deltaKind === "pp" ? fmtPP(delta) : fmtSignedPct(delta)}
          {hint ? <span className="text-slate-400"> · {hint}</span> : null}
        </div>
      )}
      {delta == null && hint && <div className="mt-1 text-xs text-slate-400">{hint}</div>}
    </div>
  );
}

export function Badge({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${className}`}
    >
      {children}
    </span>
  );
}

export function DataState({
  isLoading,
  error,
  empty,
  children,
}: {
  isLoading: boolean;
  error?: Error;
  empty?: boolean;
  children: ReactNode;
}) {
  if (error) {
    return (
      <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
        Erro ao carregar: {error.message}
      </div>
    );
  }
  if (isLoading) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-500">
        <span className="h-2 w-2 animate-pulse rounded-full bg-gold-500" />
        Carregando…
      </div>
    );
  }
  if (empty) {
    return (
      <div className="rounded-lg border border-dashed border-slate-300 p-6 text-center text-sm text-slate-400">
        Sem dados para os filtros atuais.
      </div>
    );
  }
  return <>{children}</>;
}

export function EfeitoBadge({ efeito }: { efeito: string }) {
  const map: Record<string, string> = {
    frequencia: "bg-brand-50 text-brand-700 border-brand-200",
    custo_medio: "bg-gold-50 text-gold-700 border-gold-400",
    misto: "bg-slate-100 text-slate-700 border-slate-200",
  };
  const label: Record<string, string> = {
    frequencia: "Frequência",
    custo_medio: "Custo médio",
    misto: "Misto",
  };
  return <Badge className={map[efeito] ?? map.misto}>{label[efeito] ?? efeito}</Badge>;
}

export function LinkButton({ href, children }: { href: string; children: ReactNode }) {
  return (
    <Link
      href={href}
      className="inline-flex items-center gap-1 rounded-md border border-brand-200 bg-brand-50 px-2.5 py-1 text-xs font-medium text-brand-700 hover:bg-brand-100"
    >
      {children}
    </Link>
  );
}
