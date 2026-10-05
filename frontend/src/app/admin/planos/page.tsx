"use client";

/** Matriz plano × feature — configurável (não é tabela comercial definitiva). */

import { useState } from "react";

import { Card, DataState, PageHeader, StatusBadge, Table, Td, Th, Toggle } from "@/components/ui";
import { apiSend, ApiError } from "@/lib/api";
import { useApi } from "@/lib/useApi";

interface Matriz {
  plans: { code: string; name: string; description: string; is_active: boolean; features: string[] }[];
  features: { key: string; name: string; module: string; is_active: boolean }[];
}

export default function AdminPlanosPage() {
  const { data, error, isLoading, mutate } = useMatriz();
  const [erro, setErro] = useState<string | null>(null);

  async function alternar(plan: string, feature: string, incluir: boolean) {
    setErro(null);
    try {
      const r = await apiSend<Matriz>(`/admin/plans/${plan}/features/${feature}`, "PUT", { included: incluir });
      await mutate(r, { revalidate: false });
    } catch (e) {
      setErro((e as ApiError).message);
    }
  }

  return (
    <div className="space-y-4">
      <PageHeader title="Planos" description="Cada plano define o conjunto padrão de capabilities. Nenhuma regra de negócio consulta o nome do plano — só a feature resolvida. Alterações valem imediatamente e são auditadas." />
      {erro && <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{erro}</p>}
      <Card>
        <DataState isLoading={isLoading && !data} error={error}>
          {data && (
            <Table>
              <thead>
                <tr>
                  <Th>Feature</Th>
                  {data.plans.map((p) => <Th key={p.code} className="text-center">{p.name}{!p.is_active && " (inativo)"}</Th>)}
                </tr>
              </thead>
              <tbody>
                {data.features.map((f) => (
                  <tr key={f.key}>
                    <Td>
                      <div className="font-medium">{f.name}</div>
                      <div className="text-[11px] text-slate-400">{f.module} · <span className="font-mono">{f.key}</span>
                        {!f.is_active && <StatusBadge tone="warning">desligada globalmente</StatusBadge>}</div>
                    </Td>
                    {data.plans.map((p) => (
                      <Td key={p.code} className="text-center">
                        <Toggle label={`${f.key} em ${p.code}`} checked={p.features.includes(f.key)}
                          onChange={(v) => alternar(p.code, f.key, v)} />
                      </Td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </DataState>
      </Card>
    </div>
  );
}

function useMatriz() {
  const r = useApi<Matriz>("/admin/plans");
  return { ...r, mutate: r.reload };
}
