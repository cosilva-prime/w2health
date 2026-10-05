"use client";

import Link from "next/link";
import { useState } from "react";

import {
  Button,
  Card,
  DataState,
  Dialog,
  EntityStatus,
  Field,
  Input,
  PageHeader,
  StatusBadge,
  Table,
  Td,
  Th,
} from "@/components/ui";
import { apiSend, ApiError, qs } from "@/lib/api";
import { ROLE_LABEL, useSession } from "@/lib/session";
import { useApi } from "@/lib/useApi";

interface UserItem {
  id: string;
  email: string;
  name: string;
  status: string;
  platform_role: string | null;
  mfa_enabled: boolean;
  must_change_password: boolean;
  locked: boolean;
  last_login_at: string | null;
  memberships: { tenant_id: string; tenant_name: string; role: string; status: string }[];
}

export default function AdminUsuariosPage() {
  const s = useSession();
  const [q, setQ] = useState("");
  const { data, error, isLoading, reload } = useApi<{ itens: UserItem[] }>(`/admin/users${qs({ q: q || null })}`);
  const [acao, setAcao] = useState<{ u: UserItem; tipo: "reset-password" | "reset-mfa" } | null>(null);
  const [motivo, setMotivo] = useState("");
  const [senha, setSenha] = useState<string | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  async function exec(fn: () => Promise<unknown>) {
    setErro(null);
    try {
      await fn();
      await reload();
    } catch (e) {
      setErro((e as ApiError).message);
    }
  }

  return (
    <div className="space-y-4">
      <PageHeader title="Usuários da plataforma" description="Contas de todos os tenants. Vínculos e papéis por tenant são geridos na página de cada tenant. O papel SUPER_ADMIN só é concedido via CLI administrativa." />
      {erro && <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{erro}</p>}
      <Card action={<Input placeholder="Buscar por nome ou e-mail" value={q} onChange={(e) => setQ(e.target.value)} className="w-64 py-1 text-xs" />} title="Contas">
        <DataState isLoading={isLoading && !data} error={error} empty={data?.itens.length === 0}>
          <Table>
            <thead><tr><Th>Usuário</Th><Th>Vínculos</Th><Th>Status</Th><Th>MFA</Th><Th>Último acesso</Th><Th /></tr></thead>
            <tbody>
              {data?.itens.map((u) => (
                <tr key={u.id}>
                  <Td><div className="font-medium">{u.name}</div><div className="text-xs text-slate-400">{u.email}</div>
                    {u.platform_role && <StatusBadge tone="gold">Works2Data</StatusBadge>}</Td>
                  <Td className="text-xs">
                    {u.memberships.map((m) => (
                      <div key={m.tenant_id}><Link className="text-brand-700 hover:underline" href={`/admin/tenants/${m.tenant_id}`}>{m.tenant_name}</Link> · {ROLE_LABEL[m.role] ?? m.role}{m.status !== "ACTIVE" && " (inativo)"}</div>
                    ))}
                  </Td>
                  <Td><EntityStatus status={u.status} />{u.locked && <StatusBadge tone="danger">bloqueado</StatusBadge>}{u.must_change_password && <StatusBadge tone="warning">senha temporária</StatusBadge>}</Td>
                  <Td>{u.mfa_enabled ? <StatusBadge tone="success">ativo</StatusBadge> : "—"}</Td>
                  <Td className="text-xs text-slate-500">{u.last_login_at ? new Date(u.last_login_at).toLocaleString("pt-BR") : "nunca"}</Td>
                  <Td className="whitespace-nowrap text-right">
                    {u.id !== s.me?.user.id && (
                      <div className="flex justify-end gap-1">
                        <Button size="sm" variant="ghost" onClick={() => exec(() => apiSend(`/admin/users/${u.id}`, "PATCH", { status: u.status === "ACTIVE" ? "INACTIVE" : "ACTIVE" }))}>
                          {u.status === "ACTIVE" ? "Desativar" : "Reativar"}
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => setAcao({ u, tipo: "reset-password" })}>Senha</Button>
                        {u.mfa_enabled && <Button size="sm" variant="ghost" onClick={() => setAcao({ u, tipo: "reset-mfa" })}>Reset MFA</Button>}
                      </div>
                    )}
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </DataState>
      </Card>

      <Dialog open={acao != null} title={acao?.tipo === "reset-mfa" ? "Reset administrativo de MFA" : "Gerar senha temporária"} onClose={() => setAcao(null)}>
        <form className="space-y-3" onSubmit={async (e) => {
          e.preventDefault();
          if (!acao) return;
          await exec(async () => {
            const r = await apiSend<{ temporary_password?: string }>(`/admin/users/${acao.u.id}/${acao.tipo}`, "POST", { reason: motivo });
            if (r.temporary_password) setSenha(r.temporary_password);
          });
          setAcao(null);
          setMotivo("");
        }}>
          <p>{acao?.u.name} — sessões ativas serão encerradas. Ação auditada.</p>
          <Field label="Motivo">{(id) => <Input id={id} required minLength={3} value={motivo} onChange={(e) => setMotivo(e.target.value)} />}</Field>
          <div className="flex justify-end gap-2"><Button type="button" onClick={() => setAcao(null)}>Cancelar</Button><Button type="submit" variant="danger">Confirmar</Button></div>
        </form>
      </Dialog>
      <Dialog open={senha != null} title="Senha temporária" onClose={() => setSenha(null)} footer={<Button variant="primary" onClick={() => setSenha(null)}>Entendi</Button>}>
        <p>Exibida somente agora; troca obrigatória no primeiro acesso.</p>
        <code className="mt-3 block select-all rounded bg-slate-100 p-3 text-center font-mono">{senha}</code>
      </Dialog>
    </div>
  );
}
