"use client";

import Link from "next/link";

import { Card, DataState, PageHeader, StatusBadge, EntityStatus } from "@/components/ui";
import { useApi } from "@/lib/useApi";

interface Overview {
  tenant: { id: string; name: string; legal_name: string | null; status: string; is_synthetic: boolean; created_at: string | null };
  plan: { code: string; name: string } | null;
  features: { key: string; name: string; enabled: boolean }[];
  active_users: number;
  limits: { max_users: number; max_alert_rules: number };
}

export default function GestaoPage() {
  const { data, error, isLoading } = useApi<Overview>("/tenant/overview");
  return (
    <div className="space-y-4">
      <PageHeader
        title="Informações do ambiente"
        description="Plano e recursos são contratuais e definidos pela Works2Data. Aqui você administra usuários, identidade visual e preferências do seu ambiente."
      />
      <DataState isLoading={isLoading && !data} error={error}>
        {data && (
          <div className="grid gap-4 lg:grid-cols-2">
            <Card title="Identificação">
              <dl className="grid grid-cols-[9rem_1fr] gap-y-2 text-sm">
                <dt className="text-slate-400">Nome</dt><dd>{data.tenant.name}</dd>
                <dt className="text-slate-400">Razão social</dt><dd>{data.tenant.legal_name ?? <span className="text-slate-400">Não informada</span>}</dd>
                <dt className="text-slate-400">Código</dt><dd className="font-mono text-xs">{data.tenant.id}</dd>
                <dt className="text-slate-400">Status</dt><dd><EntityStatus status={data.tenant.status} /></dd>
                <dt className="text-slate-400">Natureza dos dados</dt>
                <dd>{data.tenant.is_synthetic ? <StatusBadge tone="gold">Sintéticos (demonstração)</StatusBadge> : <StatusBadge tone="info">Dados do cliente</StatusBadge>}</dd>
                <dt className="text-slate-400">Usuários ativos</dt><dd>{data.active_users} de {data.limits.max_users}</dd>
              </dl>
            </Card>
            <Card title={`Plano ${data.plan?.name ?? "— sem plano"}`}>
              <ul className="grid gap-1 sm:grid-cols-2">
                {data.features.map((f) => (
                  <li key={f.key} className="flex items-center gap-2 text-sm">
                    <span aria-hidden className={f.enabled ? "text-emerald-600" : "text-slate-300"}>{f.enabled ? "✓" : "–"}</span>
                    <span className={f.enabled ? "text-slate-700" : "text-slate-400"}>{f.name}</span>
                  </li>
                ))}
              </ul>
              <p className="mt-3 text-xs text-slate-400">Para alterar o plano ou habilitar recursos, fale com a Works2Data.</p>
            </Card>
            <Card title="Atalhos" className="lg:col-span-2">
              <div className="flex flex-wrap gap-3 text-sm">
                <Link className="text-brand-700 hover:underline" href="/gestao/usuarios">Usuários e papéis →</Link>
                <Link className="text-brand-700 hover:underline" href="/gestao/configuracoes">Configurações →</Link>
                <Link className="text-brand-700 hover:underline" href="/configuracao/insights">Regras de alerta →</Link>
                <Link className="text-brand-700 hover:underline" href="/gestao/auditoria">Auditoria →</Link>
              </div>
            </Card>
          </div>
        )}
      </DataState>
    </div>
  );
}
