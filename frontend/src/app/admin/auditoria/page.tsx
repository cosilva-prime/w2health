"use client";

import { useState } from "react";

import { AuditItem, AuditTable } from "@/components/admin/AuditTable";
import { TenantPicker } from "@/components/admin/TenantPicker";
import { Card, DataState, Input, PageHeader, Select } from "@/components/ui";
import { qs } from "@/lib/api";
import { useApi } from "@/lib/useApi";

export default function AdminAuditoriaPage() {
  const [tenant, setTenant] = useState<string | null>(null);
  const [acao, setAcao] = useState("");
  const [resultado, setResultado] = useState("");
  const { data, error, isLoading } = useApi<{ itens: AuditItem[] }>(
    `/admin/audit${qs({ tenant_id: tenant, action: acao || null, outcome: resultado || null, limit: 300 })}`,
  );
  return (
    <div className="space-y-4">
      <PageHeader title="Auditoria da plataforma" description="Trilha imutável (append-only para a aplicação). Nunca contém senha, token, segredo MFA ou credencial." />
      <Card title="Eventos" action={
        <div className="flex flex-wrap gap-2">
          <TenantPicker value={tenant} onChange={setTenant} allowAll />
          <Input placeholder="Ação (ex.: auth.)" value={acao} onChange={(e) => setAcao(e.target.value)} className="w-40 py-1 text-xs" />
          <Select value={resultado} onChange={(e) => setResultado(e.target.value)} className="w-32 py-1 text-xs" aria-label="Resultado">
            <option value="">Todos</option><option value="success">Sucesso</option><option value="failure">Falha</option><option value="denied">Negado</option>
          </Select>
        </div>
      }>
        <DataState isLoading={isLoading && !data} error={error} empty={data?.itens.length === 0}>
          {data && <AuditTable itens={data.itens} showTenant />}
        </DataState>
      </Card>
    </div>
  );
}
