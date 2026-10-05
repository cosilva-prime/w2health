"use client";

import { useState } from "react";

import { SettingsEditor } from "@/components/admin/SettingsEditor";
import { TenantPicker } from "@/components/admin/TenantPicker";
import { PageHeader } from "@/components/ui";

export default function AdminConfiguracoesPage() {
  const [tenant, setTenant] = useState<string | null>(null);
  return (
    <div className="space-y-4">
      <PageHeader title="Configurações por tenant" description="Inclui limites contratuais (somente plataforma). Segredos ficam na página do tenant (write-only)." actions={<TenantPicker value={tenant} onChange={setTenant} />} />
      {tenant ? <SettingsEditor key={tenant} base={`/admin/tenants/${tenant}/settings`} /> : <p className="text-sm text-slate-400">Selecione um tenant.</p>}
    </div>
  );
}
