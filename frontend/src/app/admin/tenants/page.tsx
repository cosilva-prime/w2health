"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";

import {
  Button,
  Card,
  DataState,
  Dialog,
  EntityStatus,
  Field,
  Input,
  PageHeader,
  Select,
  StatusBadge,
  Table,
  Td,
  Th,
} from "@/components/ui";
import { apiSend, ApiError } from "@/lib/api";
import { useApi } from "@/lib/useApi";

export interface TenantSummary {
  id: string;
  code: string;
  uuid: string;
  name: string;
  legal_name: string | null;
  status: string;
  is_synthetic: boolean;
  plan: { code: string; name: string } | null;
  active_users: number;
  created_at: string | null;
}

export default function AdminTenantsPage() {
  const { data, error, isLoading, reload } = useApi<{ itens: TenantSummary[] }>("/admin/tenants");
  const planos = useApi<{ plans: { code: string; name: string; is_active: boolean }[] }>("/admin/plans");
  const [novo, setNovo] = useState(false);

  return (
    <div className="space-y-4">
      <PageHeader
        title="Tenants"
        description="Operadoras clientes da plataforma. Todo acesso de plataforma aos dados de um tenant é explícito e auditado."
        actions={<Button variant="primary" onClick={() => setNovo(true)}>Novo tenant</Button>}
      />
      <Card>
        <DataState isLoading={isLoading && !data} error={error} empty={data?.itens.length === 0}>
          <Table>
            <thead><tr><Th>Tenant</Th><Th>Código</Th><Th>Plano</Th><Th>Status</Th><Th>Usuários</Th><Th>Dados</Th></tr></thead>
            <tbody>
              {data?.itens.map((t) => (
                <tr key={t.id} className="hover:bg-slate-50">
                  <Td><Link href={`/admin/tenants/${t.id}`} className="font-medium text-brand-700 hover:underline">{t.name}</Link>
                    {t.legal_name && <div className="text-xs text-slate-400">{t.legal_name}</div>}</Td>
                  <Td className="font-mono text-xs">{t.code}</Td>
                  <Td>{t.plan?.name ?? <span className="text-slate-400">sem plano</span>}</Td>
                  <Td><EntityStatus status={t.status} /></Td>
                  <Td>{t.active_users}</Td>
                  <Td>{t.is_synthetic ? <StatusBadge tone="gold">sintéticos</StatusBadge> : <StatusBadge tone="info">cliente</StatusBadge>}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </DataState>
      </Card>
      <NovoTenant open={novo} onClose={() => setNovo(false)} planos={planos.data?.plans ?? []}
        onCreated={async () => { setNovo(false); await reload(); }} />
    </div>
  );
}

function NovoTenant({ open, onClose, planos, onCreated }: {
  open: boolean;
  onClose: () => void;
  planos: { code: string; name: string; is_active: boolean }[];
  onCreated: () => void;
}) {
  const [f, setF] = useState({ code: "", name: "", legal_name: "", plan_code: "", is_synthetic: false });
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function enviar(e: FormEvent) {
    e.preventDefault();
    setErro(null);
    setEnviando(true);
    try {
      await apiSend("/admin/tenants", "POST", {
        ...f, legal_name: f.legal_name || null, plan_code: f.plan_code || null,
      });
      setF({ code: "", name: "", legal_name: "", plan_code: "", is_synthetic: false });
      onCreated();
    } catch (err) {
      setErro((err as ApiError).message);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Dialog open={open} title="Novo tenant" onClose={onClose}>
      <form onSubmit={enviar} className="space-y-3">
        {erro && <p className="rounded-md bg-rose-50 px-3 py-2 text-rose-700">{erro}</p>}
        <Field label="Código (imutável)" hint="minúsculas, números e hífen — ex.: operadora-alfa">
          {(id) => <Input id={id} required pattern="[a-z0-9][a-z0-9-]{1,38}[a-z0-9]" value={f.code} onChange={(e) => setF({ ...f, code: e.target.value })} />}
        </Field>
        <Field label="Nome">{(id) => <Input id={id} required minLength={2} value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} />}</Field>
        <Field label="Razão social (opcional)">{(id) => <Input id={id} value={f.legal_name} onChange={(e) => setF({ ...f, legal_name: e.target.value })} />}</Field>
        <Field label="Plano">
          {(id) => (
            <Select id={id} value={f.plan_code} onChange={(e) => setF({ ...f, plan_code: e.target.value })}>
              <option value="">— sem plano (nenhuma feature) —</option>
              {planos.filter((p) => p.is_active).map((p) => <option key={p.code} value={p.code}>{p.name}</option>)}
            </Select>
          )}
        </Field>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.is_synthetic} onChange={(e) => setF({ ...f, is_synthetic: e.target.checked })} /> Ambiente com dados sintéticos (demonstração)</label>
        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" onClick={onClose}>Cancelar</Button>
          <Button type="submit" variant="primary" loading={enviando}>Criar</Button>
        </div>
      </form>
    </Dialog>
  );
}
