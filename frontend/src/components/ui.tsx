"use client";

/**
 * Design system mínimo do W2Health (Fundação SaaS V1).
 *
 * Princípios: executivo, denso sem poluição, sem efeitos excessivos. Tipografia do sistema,
 * espaçamento em múltiplos de 4 px, cantos `rounded-lg/xl`, bordas `slate-200`, sombras
 * leves. Cores de marca via `brand-*`/`gold-*` (Works2Data) e `tenant-*` (variáveis CSS do
 * branding do cliente — nunca CSS arbitrário).
 *
 * Estados padronizados (nunca tela em branco): Loading · Empty · Error · Forbidden ·
 * FeatureUnavailable · TenantSuspended · SessionExpired — `DataState` escolhe pelo `code`
 * estável que o backend devolve.
 */

import Link from "next/link";
import {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  useEffect,
  useId,
  useRef,
} from "react";

import { ApiError } from "@/lib/api";
import { fmtPP, fmtSignedPct } from "@/lib/format";

// ===================================================================== superfícies
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
        <header className="flex items-center justify-between gap-3 border-b border-slate-100 px-4 py-3">
          <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
          {action}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h2 className="text-base font-semibold text-slate-900">{title}</h2>
        {description && <p className="mt-0.5 max-w-3xl text-sm text-slate-500">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

// ===================================================================== KPI
export function Stat({
  label,
  value,
  delta,
  deltaKind = "pp",
  hint,
  invertColors = false,
  href,
  info,
}: {
  label: string;
  value: ReactNode;
  delta?: number | null;
  deltaKind?: "pp" | "pct";
  hint?: string;
  invertColors?: boolean;
  href?: string;
  /** Slot de transparência (ex.: <KpiInfo kpi="sinistralidade_liquida" />). */
  info?: ReactNode;
}) {
  const good = delta == null ? null : invertColors ? delta > 0 : delta < 0;
  const color =
    good == null ? "text-slate-400" : good ? "text-emerald-600" : "text-rose-600";
  return (
    <div className={`rounded-xl border border-slate-200 bg-white p-4 shadow-sm ${href ? "transition hover:border-brand-300 hover:shadow" : ""}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</div>
        {info}
      </div>
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

// ===================================================================== badges
export function Badge({
  children,
  className = "",
  title,
}: {
  children: ReactNode;
  className?: string;
  title?: string;
}) {
  return (
    <span
      title={title}
      className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${className}`}
    >
      {children}
    </span>
  );
}

const TONE: Record<string, string> = {
  neutral: "bg-slate-50 text-slate-700 border-slate-200",
  success: "bg-emerald-50 text-emerald-700 border-emerald-200",
  warning: "bg-amber-50 text-amber-800 border-amber-200",
  danger: "bg-rose-50 text-rose-700 border-rose-200",
  info: "bg-brand-50 text-brand-700 border-brand-200",
  gold: "bg-gold-50 text-gold-700 border-gold-400",
};

export function StatusBadge({ tone = "neutral", children, title }: {
  tone?: keyof typeof TONE;
  children: ReactNode;
  title?: string;
}) {
  return <Badge className={TONE[tone]} title={title}>{children}</Badge>;
}

const STATUS_TONE: Record<string, keyof typeof TONE> = {
  ACTIVE: "success", SUSPENDED: "warning", INACTIVE: "neutral",
};
const STATUS_LABEL: Record<string, string> = {
  ACTIVE: "Ativo", SUSPENDED: "Suspenso", INACTIVE: "Inativo",
};

export function EntityStatus({ status }: { status: string }) {
  return <StatusBadge tone={STATUS_TONE[status] ?? "neutral"}>{STATUS_LABEL[status] ?? status}</StatusBadge>;
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

// ===================================================================== botões e campos
type Variant = "primary" | "secondary" | "ghost" | "danger";
const BTN: Record<Variant, string> = {
  primary: "bg-brand-800 text-white hover:bg-brand-700 border-brand-800",
  secondary: "bg-white text-slate-700 hover:bg-slate-50 border-slate-300",
  ghost: "bg-transparent text-slate-600 hover:bg-slate-100 border-transparent",
  danger: "bg-white text-rose-700 hover:bg-rose-50 border-rose-300",
};

export function Button({
  variant = "secondary",
  size = "md",
  loading = false,
  className = "",
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: "sm" | "md";
  loading?: boolean;
}) {
  const sz = size === "sm" ? "px-2.5 py-1 text-xs" : "px-3.5 py-2 text-sm";
  return (
    <button
      {...rest}
      disabled={rest.disabled || loading}
      className={`inline-flex items-center justify-center gap-1.5 rounded-md border font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${sz} ${BTN[variant]} ${className}`}
    >
      {loading && <Spinner small />}
      {children}
    </button>
  );
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

export function Field({
  label,
  hint,
  error,
  children,
}: {
  label: string;
  hint?: ReactNode;
  error?: string | null;
  children: (id: string) => ReactNode;
}) {
  const id = useId();
  return (
    <div className="space-y-1">
      <label htmlFor={id} className="block text-xs font-medium text-slate-600">
        {label}
      </label>
      {children(id)}
      {error ? (
        <p className="text-xs text-rose-600">{error}</p>
      ) : hint ? (
        <p className="text-xs text-slate-400">{hint}</p>
      ) : null}
    </div>
  );
}

const INPUT =
  "w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm placeholder:text-slate-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100 disabled:bg-slate-50";

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={`${INPUT} ${props.className ?? ""}`} />;
}

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={`${INPUT} ${props.className ?? ""}`} />;
}

export function Toggle({
  checked,
  onChange,
  disabled,
  label,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
  label: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors disabled:opacity-40 ${checked ? "bg-emerald-500" : "bg-slate-300"}`}
    >
      <span className={`inline-block h-4 w-4 rounded-full bg-white shadow transition-transform ${checked ? "translate-x-4" : "translate-x-0.5"}`} />
    </button>
  );
}

// ===================================================================== tabela
export function Table({ children }: { children: ReactNode }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">{children}</table>
    </div>
  );
}

export function Th({ children, className = "" }: { children?: ReactNode; className?: string }) {
  return (
    <th className={`border-b border-slate-200 px-3 py-2 text-xs font-medium uppercase tracking-wide text-slate-400 ${className}`}>
      {children}
    </th>
  );
}

export function Td({ children, className = "" }: { children?: ReactNode; className?: string }) {
  return <td className={`border-b border-slate-100 px-3 py-2 align-middle text-slate-700 ${className}`}>{children}</td>;
}

// ===================================================================== diálogo e tooltip
export function Dialog({
  open,
  title,
  onClose,
  children,
  footer,
  wide = false,
}: {
  open: boolean;
  title: ReactNode;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    ref.current?.focus();
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4" onMouseDown={onClose}>
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        tabIndex={-1}
        onMouseDown={(e) => e.stopPropagation()}
        className={`max-h-[90vh] w-full overflow-y-auto rounded-xl bg-white shadow-xl outline-none ${wide ? "max-w-2xl" : "max-w-md"}`}
      >
        <header className="flex items-center justify-between border-b border-slate-100 px-5 py-3">
          <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
          <button onClick={onClose} aria-label="Fechar" className="text-slate-400 hover:text-slate-700">
            ✕
          </button>
        </header>
        <div className="px-5 py-4 text-sm text-slate-700">{children}</div>
        {footer && <footer className="flex justify-end gap-2 border-t border-slate-100 px-5 py-3">{footer}</footer>}
      </div>
    </div>
  );
}

export function Tooltip({ text, children }: { text: string; children: ReactNode }) {
  return (
    <span className="group relative inline-flex">
      {children}
      <span
        role="tooltip"
        className="pointer-events-none absolute bottom-full left-1/2 z-40 mb-1 hidden w-max max-w-xs -translate-x-1/2 rounded-md bg-slate-900 px-2 py-1 text-[11px] text-white shadow group-hover:block group-focus-within:block"
      >
        {text}
      </span>
    </span>
  );
}

// ===================================================================== estados
export function Spinner({ small = false }: { small?: boolean }) {
  return (
    <span
      aria-hidden
      className={`inline-block animate-spin rounded-full border-2 border-slate-300 border-t-brand-700 ${small ? "h-3 w-3" : "h-4 w-4"}`}
    />
  );
}

export function LoadingState({ label = "Carregando…" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-500">
      <span className="h-2 w-2 animate-pulse rounded-full bg-gold-500" />
      {label}
    </div>
  );
}

export function EmptyState({ title = "Sem dados para os filtros atuais.", children }: {
  title?: string;
  children?: ReactNode;
}) {
  return (
    <div className="rounded-lg border border-dashed border-slate-300 p-6 text-center text-sm text-slate-400">
      {title}
      {children && <div className="mt-2">{children}</div>}
    </div>
  );
}

function StateBox({ icon, title, children, tone = "slate" }: {
  icon: string;
  title: string;
  children?: ReactNode;
  tone?: "slate" | "rose" | "amber";
}) {
  const tones = {
    slate: "border-slate-200 bg-white text-slate-600",
    rose: "border-rose-200 bg-rose-50 text-rose-700",
    amber: "border-amber-200 bg-amber-50 text-amber-800",
  };
  return (
    <div role="status" className={`rounded-xl border p-6 text-center ${tones[tone]}`}>
      <div aria-hidden className="text-2xl">{icon}</div>
      <div className="mt-2 text-sm font-semibold">{title}</div>
      {children && <div className="mx-auto mt-1 max-w-md text-sm opacity-90">{children}</div>}
    </div>
  );
}

export function ErrorState({ message, requestHint = true }: { message?: string; requestHint?: boolean }) {
  return (
    <StateBox icon="⚠" title="Não foi possível carregar" tone="rose">
      {message ?? "Ocorreu um erro inesperado."}
      {requestHint && <div className="mt-1 text-xs opacity-75">Tente novamente em instantes.</div>}
    </StateBox>
  );
}

export function ForbiddenState() {
  return (
    <StateBox icon="🔒" title="Acesso não permitido">
      Seu perfil não tem permissão para esta área. Fale com o administrador do ambiente.
    </StateBox>
  );
}

export function FeatureUnavailableState({ feature }: { feature?: string }) {
  return (
    <StateBox icon="◇" title="Recurso não disponível no plano contratado">
      Este módulo não está habilitado para o seu ambiente.
      {feature && <div className="mt-1 font-mono text-xs opacity-70">{feature}</div>}
    </StateBox>
  );
}

export function TenantSuspendedState() {
  return (
    <StateBox icon="⏸" title="Ambiente suspenso" tone="amber">
      O acesso a este ambiente está temporariamente suspenso. Procure o administrador ou a
      equipe Works2Data.
    </StateBox>
  );
}

export function SessionExpiredState({ onLogin }: { onLogin: () => void }) {
  return (
    <StateBox icon="⌛" title="Sua sessão expirou">
      Por segurança, entre novamente para continuar.
      <div className="mt-3">
        <Button variant="primary" onClick={onLogin}>Entrar novamente</Button>
      </div>
    </StateBox>
  );
}

/** Estado de erro escolhido pelo `code` estável devolvido pelo backend. */
export function ApiErrorState({ error }: { error: Error }) {
  const e = error as ApiError;
  switch (e.code) {
    case "forbidden":
      return <ForbiddenState />;
    case "feature_unavailable":
      return <FeatureUnavailableState feature={e.feature} />;
    case "tenant_suspended":
      return <TenantSuspendedState />;
    case "not_found":
      return <EmptyState title="Registro não encontrado neste ambiente." />;
    default:
      return <ErrorState message={e.message} />;
  }
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
  if (error) return <ApiErrorState error={error} />;
  if (isLoading) return <LoadingState />;
  if (empty) return <EmptyState />;
  return <>{children}</>;
}

/** Aviso padrão quando o backend omitiu blocos por plano (`restricoes_plano`). */
export function PlanRestrictionNote({ restricoes }: { restricoes?: string[] | null }) {
  if (!restricoes || restricoes.length === 0) return null;
  const nomes: Record<string, string> = {
    beneficiary_intelligence: "beneficiários",
    provider_intelligence: "prestadores",
    contract_intelligence: "contratos",
    alerts: "alertas",
    insights: "insights",
  };
  return (
    <p className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-500">
      Detalhamento por {restricoes.map((r) => nomes[r] ?? r).join(", ")} não disponível no plano
      contratado — os cálculos acima não mudam.
    </p>
  );
}
