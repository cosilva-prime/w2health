"use client";

import { useState } from "react";

import { Card, DataState, PageHeader, StatusBadge, Table, Td, Th, Toggle } from "@/components/ui";
import { apiSend, ApiError } from "@/lib/api";
import { useApi } from "@/lib/useApi";

interface Item { key: string; name: string; description: string; module: string; is_active: boolean; implemented: boolean }

export default function AdminFeaturesPage() {
  const { data, error, isLoading, reload } = useApi<{ itens: Item[] }>("/admin/features");
  const [erro, setErro] = useState<string | null>(null);
  return (
    <div className="space-y-4">
      <PageHeader title="Features" description="Catálogo de capabilities existentes no código. Desligar uma feature aqui é um kill switch GLOBAL: vale para todos os tenants, acima de plano e override." />
      {erro && <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{erro}</p>}
      <Card>
        <DataState isLoading={isLoading && !data} error={error}>
          <Table>
            <thead><tr><Th>Feature</Th><Th>Módulo</Th><Th>Descrição</Th><Th className="text-center">Ativa</Th></tr></thead>
            <tbody>
              {data?.itens.map((f) => (
                <tr key={f.key}>
                  <Td><div className="font-medium">{f.name}</div><div className="font-mono text-[11px] text-slate-400">{f.key}</div>
                    {!f.implemented && <StatusBadge tone="warning">sem implementação</StatusBadge>}</Td>
                  <Td className="text-xs">{f.module}</Td>
                  <Td className="max-w-md text-xs text-slate-500">{f.description}</Td>
                  <Td className="text-center">
                    <Toggle label={`ativar ${f.key}`} checked={f.is_active} onChange={async (v) => {
                      setErro(null);
                      try {
                        await apiSend(`/admin/features/${f.key}`, "PATCH", { is_active: v });
                        await reload();
                      } catch (e) {
                        setErro((e as ApiError).message);
                      }
                    }} />
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </DataState>
      </Card>
    </div>
  );
}
