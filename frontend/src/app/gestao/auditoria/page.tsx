"use client";

import { useState } from "react";

import { AuditItem, AuditTable } from "@/components/admin/AuditTable";
import { Card, DataState, Input, PageHeader } from "@/components/ui";
import { qs } from "@/lib/api";
import { useApi } from "@/lib/useApi";

export default function GestaoAuditoriaPage() {
  const [acao, setAcao] = useState("");
  const { data, error, isLoading } = useApi<{ itens: AuditItem[] }>(`/tenant/audit${qs({ action: acao || null, limit: 200 })}`);
  return (
    <div className="space-y-4">
      <PageHeader title="Auditoria do ambiente" description="Registros imutáveis de acesso e administração deste ambiente. Senhas, tokens e segredos nunca são registrados." />
      <Card title="Eventos" action={<Input placeholder="Filtrar ação (ex.: user.)" value={acao} onChange={(e) => setAcao(e.target.value)} className="w-56 py-1 text-xs" />}>
        <DataState isLoading={isLoading && !data} error={error} empty={data?.itens.length === 0}>
          {data && <AuditTable itens={data.itens} />}
        </DataState>
      </Card>
    </div>
  );
}
