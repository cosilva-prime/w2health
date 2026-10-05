"use client";

import { SettingsEditor } from "@/components/admin/SettingsEditor";
import { PageHeader } from "@/components/ui";
import { useSession } from "@/lib/session";

export default function GestaoConfiguracoesPage() {
  const s = useSession();
  return (
    <div className="space-y-4">
      <PageHeader title="Configurações do ambiente" description="Preferências de análise e de segurança. Limites contratuais são definidos pela Works2Data." />
      <SettingsEditor base="/tenant/settings" readOnly={!s.can("tenant_settings:manage")} onSaved={() => s.reload()} />
    </div>
  );
}
