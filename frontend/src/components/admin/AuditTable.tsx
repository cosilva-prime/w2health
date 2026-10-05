"use client";

import { StatusBadge, Table, Td, Th } from "@/components/ui";

export interface AuditItem {
  id: number;
  occurred_at: string | null;
  actor_email: string | null;
  actor_role: string | null;
  tenant_id: string | null;
  action: string;
  entity_type: string | null;
  entity_id: string | null;
  outcome: "success" | "failure" | "denied";
  ip: string | null;
  request_id: string | null;
  details: Record<string, unknown>;
}

const OUTCOME = { success: "success", failure: "danger", denied: "warning" } as const;
const OUTCOME_LABEL = { success: "sucesso", failure: "falha", denied: "negado" };

export function AuditTable({ itens, showTenant = false }: { itens: AuditItem[]; showTenant?: boolean }) {
  return (
    <Table>
      <thead>
        <tr>
          <Th>Quando</Th><Th>Ator</Th>{showTenant && <Th>Tenant</Th>}<Th>Ação</Th><Th>Entidade</Th><Th>Resultado</Th><Th>Detalhes</Th>
        </tr>
      </thead>
      <tbody>
        {itens.map((a) => (
          <tr key={a.id}>
            <Td className="whitespace-nowrap text-xs text-slate-500">{a.occurred_at ? new Date(a.occurred_at).toLocaleString("pt-BR") : "—"}</Td>
            <Td className="text-xs">{a.actor_email ?? "—"}{a.actor_role && <div className="text-slate-400">{a.actor_role}</div>}</Td>
            {showTenant && <Td className="text-xs">{a.tenant_id ?? "—"}</Td>}
            <Td className="font-mono text-xs">{a.action}</Td>
            <Td className="text-xs">{a.entity_type ? `${a.entity_type}${a.entity_id ? ` · ${a.entity_id.slice(0, 18)}` : ""}` : "—"}</Td>
            <Td><StatusBadge tone={OUTCOME[a.outcome]}>{OUTCOME_LABEL[a.outcome]}</StatusBadge></Td>
            <Td className="max-w-xs truncate font-mono text-[11px] text-slate-500" >
              <span title={JSON.stringify(a.details)}>{Object.keys(a.details ?? {}).length ? JSON.stringify(a.details) : "—"}</span>
            </Td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}
