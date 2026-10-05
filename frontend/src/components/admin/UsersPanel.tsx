"use client";

import { FormEvent, useState } from "react";

import {
  Button,
  Card,
  DataState,
  Dialog,
  EntityStatus,
  Field,
  Input,
  Select,
  StatusBadge,
  Table,
  Td,
  Th,
} from "@/components/ui";
import { apiSend, ApiError } from "@/lib/api";
import { ROLE_LABEL } from "@/lib/session";
import { useApi } from "@/lib/useApi";

export interface Member {
  user_id: string;
  email: string;
  name: string;
  role: string;
  membership_status: string;
  user_status: string;
  mfa_enabled: boolean;
  must_change_password: boolean;
  last_login_at: string | null;
}

const ROLES = ["TENANT_ADMIN", "MANAGER", "VIEWER"];

/**
 * Usuários de UM tenant. `base` = "/tenant" (gestão do tenant) ou "/admin/tenants/{id}"
 * (plataforma). `resetBase` = "/tenant/users" ou "/admin/users". O backend decide o que
 * cada perfil pode fazer; a tela só reflete.
 */
export function UsersPanel({
  base,
  resetBase,
  currentUserId,
  canManage,
}: {
  base: string;
  resetBase: string;
  currentUserId?: string;
  canManage: boolean;
}) {
  const { data, error, isLoading, reload } = useApi<{ itens: Member[] }>(`${base}/users`);
  const [novo, setNovo] = useState(false);
  const [senhaTemp, setSenhaTemp] = useState<{ email: string; senha: string } | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [reset, setReset] = useState<{ m: Member; tipo: "reset-password" | "reset-mfa" } | null>(null);

  async function alterar(m: Member, patch: { role?: string; status?: string }) {
    setErro(null);
    try {
      await apiSend(`${base}/users/${m.user_id}`, "PATCH", patch);
      await reload();
    } catch (e) {
      setErro((e as ApiError).message);
    }
  }

  return (
    <Card
      title="Usuários"
      action={canManage && <Button size="sm" variant="primary" onClick={() => setNovo(true)}>Adicionar usuário</Button>}
    >
      {erro && <p className="mb-3 rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{erro}</p>}
      <DataState isLoading={isLoading && !data} error={error} empty={data?.itens.length === 0}>
        <Table>
          <thead>
            <tr><Th>Usuário</Th><Th>Papel</Th><Th>Status</Th><Th>MFA</Th><Th>Último acesso</Th>{canManage && <Th />}</tr>
          </thead>
          <tbody>
            {data?.itens.map((m) => {
              const proprio = m.user_id === currentUserId;
              return (
                <tr key={m.user_id}>
                  <Td>
                    <div className="font-medium text-slate-800">{m.name}</div>
                    <div className="text-xs text-slate-400">{m.email}</div>
                  </Td>
                  <Td>
                    {canManage && !proprio ? (
                      <Select value={m.role} onChange={(e) => alterar(m, { role: e.target.value })} className="py-1 text-xs" aria-label="Papel">
                        {ROLES.map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}
                      </Select>
                    ) : (
                      ROLE_LABEL[m.role] ?? m.role
                    )}
                  </Td>
                  <Td>
                    <EntityStatus status={m.membership_status === "ACTIVE" && m.user_status === "ACTIVE" ? "ACTIVE" : "INACTIVE"} />
                    {m.must_change_password && <StatusBadge tone="warning">senha temporária</StatusBadge>}
                  </Td>
                  <Td>{m.mfa_enabled ? <StatusBadge tone="success">ativo</StatusBadge> : <StatusBadge>—</StatusBadge>}</Td>
                  <Td className="text-xs text-slate-500">{m.last_login_at ? new Date(m.last_login_at).toLocaleString("pt-BR") : "nunca"}</Td>
                  {canManage && (
                    <Td className="whitespace-nowrap text-right">
                      {!proprio && (
                        <div className="flex justify-end gap-1">
                          <Button size="sm" variant="ghost" onClick={() => alterar(m, { status: m.membership_status === "ACTIVE" ? "INACTIVE" : "ACTIVE" })}>
                            {m.membership_status === "ACTIVE" ? "Desativar" : "Reativar"}
                          </Button>
                          <Button size="sm" variant="ghost" onClick={() => setReset({ m, tipo: "reset-password" })}>Senha</Button>
                          {m.mfa_enabled && <Button size="sm" variant="ghost" onClick={() => setReset({ m, tipo: "reset-mfa" })}>Reset MFA</Button>}
                        </div>
                      )}
                    </Td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </Table>
      </DataState>

      <NovoUsuarioDialog
        open={novo}
        base={base}
        onClose={() => setNovo(false)}
        onCreated={async (email, senha) => {
          setNovo(false);
          if (senha) setSenhaTemp({ email, senha });
          await reload();
        }}
      />
      <ResetDialog
        alvo={reset}
        resetBase={resetBase}
        onClose={() => setReset(null)}
        onDone={async (senha) => {
          if (senha && reset) setSenhaTemp({ email: reset.m.email, senha });
          setReset(null);
          await reload();
        }}
      />
      <Dialog open={senhaTemp != null} title="Senha temporária" onClose={() => setSenhaTemp(null)}
        footer={<Button variant="primary" onClick={() => setSenhaTemp(null)}>Entendi</Button>}>
        <p>Entregue esta senha por um canal seguro a <b>{senhaTemp?.email}</b>. Ela é exibida
          <b> somente agora</b> e deverá ser trocada no primeiro acesso.</p>
        <code className="mt-3 block select-all rounded bg-slate-100 p-3 text-center font-mono text-base">{senhaTemp?.senha}</code>
      </Dialog>
    </Card>
  );
}

function NovoUsuarioDialog({ open, base, onClose, onCreated }: {
  open: boolean;
  base: string;
  onClose: () => void;
  onCreated: (email: string, senha: string | null) => void;
}) {
  const [email, setEmail] = useState("");
  const [nome, setNome] = useState("");
  const [role, setRole] = useState("VIEWER");
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function enviar(e: FormEvent) {
    e.preventDefault();
    setErro(null);
    setEnviando(true);
    try {
      const r = await apiSend<{ temporary_password: string | null }>(`${base}/users`, "POST", { email, name: nome, role });
      onCreated(email, r.temporary_password);
      setEmail(""); setNome(""); setRole("VIEWER");
    } catch (err) {
      setErro((err as ApiError).message);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Dialog open={open} title="Adicionar usuário" onClose={onClose}>
      <form onSubmit={enviar} className="space-y-3">
        {erro && <p className="rounded-md bg-rose-50 px-3 py-2 text-rose-700">{erro}</p>}
        <Field label="E-mail">{(id) => <Input id={id} type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />}</Field>
        <Field label="Nome">{(id) => <Input id={id} required minLength={2} value={nome} onChange={(e) => setNome(e.target.value)} />}</Field>
        <Field label="Papel" hint="Gestor: análises e regras de alerta. Leitor: somente leitura.">
          {(id) => (
            <Select id={id} value={role} onChange={(e) => setRole(e.target.value)}>
              {ROLES.map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}
            </Select>
          )}
        </Field>
        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" onClick={onClose}>Cancelar</Button>
          <Button type="submit" variant="primary" loading={enviando}>Adicionar</Button>
        </div>
      </form>
    </Dialog>
  );
}

function ResetDialog({ alvo, resetBase, onClose, onDone }: {
  alvo: { m: Member; tipo: "reset-password" | "reset-mfa" } | null;
  resetBase: string;
  onClose: () => void;
  onDone: (senha: string | null) => void;
}) {
  const [motivo, setMotivo] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  if (!alvo) return null;
  const titulo = alvo.tipo === "reset-password" ? "Gerar senha temporária" : "Resetar MFA";
  return (
    <Dialog open title={titulo} onClose={onClose}>
      <form className="space-y-3" onSubmit={async (e) => {
        e.preventDefault();
        setErro(null);
        setEnviando(true);
        try {
          const r = await apiSend<{ temporary_password?: string }>(`${resetBase}/${alvo.m.user_id}/${alvo.tipo}`, "POST", { reason: motivo });
          setMotivo("");
          onDone(r.temporary_password ?? null);
        } catch (err) {
          setErro((err as ApiError).message);
        } finally {
          setEnviando(false);
        }
      }}>
        <p>{alvo.m.name} ({alvo.m.email}) — as sessões ativas do usuário serão encerradas. A ação é registrada na auditoria.</p>
        {erro && <p className="rounded-md bg-rose-50 px-3 py-2 text-rose-700">{erro}</p>}
        <Field label="Motivo (obrigatório)">{(id) => <Input id={id} required minLength={3} value={motivo} onChange={(e) => setMotivo(e.target.value)} />}</Field>
        <div className="flex justify-end gap-2">
          <Button type="button" onClick={onClose}>Cancelar</Button>
          <Button type="submit" variant="danger" loading={enviando}>Confirmar</Button>
        </div>
      </form>
    </Dialog>
  );
}
