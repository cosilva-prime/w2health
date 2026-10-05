"use client";

import { useState } from "react";

import { BrandingEditor } from "@/components/admin/BrandingEditor";
import { TenantPicker } from "@/components/admin/TenantPicker";
import { PageHeader } from "@/components/ui";

export default function AdminIdentidadePage() {
  const [tenant, setTenant] = useState<string | null>(null);
  return (
    <div className="space-y-4">
      <PageHeader title="Branding por tenant" description="A plataforma pode ajustar a identidade de qualquer tenant, inclusive sem a feature de identidade visual do cliente." actions={<TenantPicker value={tenant} onChange={setTenant} />} />
      {tenant ? <BrandingEditor key={tenant} base={`/admin/tenants/${tenant}/branding`} /> : <p className="text-sm text-slate-400">Selecione um tenant.</p>}
    </div>
  );
}
