"use client";

import { FormEvent, useState } from "react";

import { RecoveryCodes } from "@/components/RecoveryCodes";
import { Button, Card, Field, Input, PageHeader, StatusBadge } from "@/components/ui";
import { apiSend, ApiError, setAccessToken } from "@/lib/api";
import { ROLE_LABEL, useSession } from "@/lib/session";

export default function ContaPage() {
  const s = useSession();
  const me = s.me!;
  return (
    <div className="max-w-3xl space-y-4">
      <PageHeader title="Minha conta" description="Dados de acesso, autenticação em dois fatores e ambientes." />
      <Card title="Identificação">
        <dl className="grid grid-cols-[10rem_1fr] gap-y-2 text-sm">
          <dt className="text-slate-400">Nome</dt><dd>{me.user.name}</dd>
          <dt className="text-slate-400">E-mail</dt><dd>{me.user.email}</dd>
          {me.user.platform_role && (<><dt className="text-slate-400">Perfil de plataforma</dt><dd><StatusBadge tone="gold">Works2Data</StatusBadge></dd></>)}
          <dt className="text-slate-400">Ambientes</dt>
          <dd className="space-y-1">
            {me.memberships.length === 0 && <span className="text-slate-400">Nenhum vínculo</span>}
            {me.memberships.map((m) => (
              <div key={m.tenant_id} className="flex items-center gap-2">
                {m.tenant_name} <StatusBadge tone="info">{ROLE_LABEL[m.role] ?? m.role}</StatusBadge>
                {m.tenant_status !== "ACTIVE" && <StatusBadge tone="warning">suspenso</StatusBadge>}
              </div>
            ))}
          </dd>
        </dl>
      </Card>
      <MfaCard />
      <SenhaCard />
    </div>
  );
}

function SenhaCard() {
  const [atual, setAtual] = useState("");
  const [nova, setNova] = useState("");
  const [conf, setConf] = useState("");
  const [msg, setMsg] = useState<{ ok: boolean; texto: string } | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function salvar(e: FormEvent) {
    e.preventDefault();
    setMsg(null);
    if (nova !== conf) return setMsg({ ok: false, texto: "As senhas não conferem." });
    setEnviando(true);
    try {
      const r = await apiSend<{ access_token: string }>("/auth/password", "POST", {
        current_password: atual, new_password: nova,
      });
      setAccessToken(r.access_token);
      setAtual(""); setNova(""); setConf("");
      setMsg({ ok: true, texto: "Senha alterada. As demais sessões foram encerradas." });
    } catch (err) {
      setMsg({ ok: false, texto: (err as ApiError).message });
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Card title="Trocar senha">
      <form onSubmit={salvar} className="grid gap-3 sm:grid-cols-3">
        <Field label="Senha atual">{(id) => <Input id={id} type="password" autoComplete="current-password" required value={atual} onChange={(e) => setAtual(e.target.value)} />}</Field>
        <Field label="Nova senha" hint="Mínimo de 12 caracteres.">{(id) => <Input id={id} type="password" autoComplete="new-password" required value={nova} onChange={(e) => setNova(e.target.value)} />}</Field>
        <Field label="Confirmação">{(id) => <Input id={id} type="password" autoComplete="new-password" required value={conf} onChange={(e) => setConf(e.target.value)} />}</Field>
        <div className="sm:col-span-3 flex items-center gap-3">
          <Button type="submit" variant="primary" loading={enviando}>Alterar senha</Button>
          {msg && <span className={`text-sm ${msg.ok ? "text-emerald-700" : "text-rose-700"}`}>{msg.texto}</span>}
        </div>
      </form>
    </Card>
  );
}

function MfaCard() {
  const s = useSession();
  const ativo = s.me!.user.mfa_enabled;
  const [setup, setSetup] = useState<{ qr_svg: string; secret: string } | null>(null);
  const [codigo, setCodigo] = useState("");
  const [senha, setSenha] = useState("");
  const [msg, setMsg] = useState<{ ok: boolean; texto: string } | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [codigos, setCodigos] = useState<string[] | null>(null);
  const [codigoRegen, setCodigoRegen] = useState("");

  async function run(fn: () => Promise<void>) {
    setMsg(null);
    setEnviando(true);
    try {
      await fn();
    } catch (err) {
      setMsg({ ok: false, texto: (err as ApiError).message });
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Card title="Autenticação em dois fatores (TOTP)"
      action={<StatusBadge tone={ativo ? "success" : "warning"}>{ativo ? "Ativa" : "Desativada"}</StatusBadge>}>
      {!ativo && !setup && (
        <div className="space-y-3 text-sm text-slate-600">
          <p>Proteja sua conta com um código gerado no celular. Recomendado para todos os usuários e obrigatório para a equipe Works2Data.</p>
          <Button variant="primary" loading={enviando} onClick={() => run(async () => {
            setSetup(await apiSend("/auth/mfa/setup", "POST", {}));
          })}>Configurar MFA</Button>
        </div>
      )}
      {!ativo && setup && (
        <form className="grid gap-4 sm:grid-cols-[auto_1fr]" onSubmit={(e) => {
          e.preventDefault();
          run(async () => {
            const r = await apiSend<{ recovery_codes?: string[] }>("/auth/mfa/confirm", "POST", { code: codigo });
            setSetup(null); setCodigo("");
            setCodigos(r.recovery_codes ?? null);
            await s.reload();
            setMsg({ ok: true, texto: "MFA ativado." });
          });
        }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={setup.qr_svg} alt="QR Code do autenticador" className="h-40 w-40" />
          <div className="space-y-3">
            <p className="text-sm text-slate-600">Escaneie o QR Code e informe o código de 6 dígitos.</p>
            <details className="text-xs text-slate-500"><summary className="cursor-pointer">Chave para digitação manual</summary>
              <code className="mt-1 block break-all font-mono">{setup.secret}</code></details>
            <Field label="Código">{(id) => <Input id={id} inputMode="numeric" maxLength={6} required value={codigo} onChange={(e) => setCodigo(e.target.value.replace(/\D/g, ""))} />}</Field>
            <Button type="submit" variant="primary" loading={enviando}>Confirmar</Button>
          </div>
        </form>
      )}
      {ativo && codigos && <div className="mb-4"><RecoveryCodes codes={codigos} onDone={() => setCodigos(null)} /></div>}
      {ativo && !codigos && (
        <form className="mb-4 grid gap-3 border-b border-slate-100 pb-4 sm:grid-cols-3" onSubmit={(e) => {
          e.preventDefault();
          run(async () => {
            const r = await apiSend<{ recovery_codes: string[] }>("/auth/mfa/recovery-codes", "POST", { code: codigoRegen });
            setCodigoRegen("");
            setCodigos(r.recovery_codes);
            await s.reload();
          });
        }}>
          <p className="text-sm text-slate-600 sm:col-span-3">
            Códigos de recuperação restantes: <b>{s.me!.user.recovery_codes_remaining}</b>. Gerar novos códigos invalida os anteriores.
          </p>
          <Field label="Código atual do autenticador">{(id) => <Input id={id} inputMode="numeric" maxLength={6} required value={codigoRegen} onChange={(e) => setCodigoRegen(e.target.value.replace(/\D/g, ""))} />}</Field>
          <div className="flex items-end"><Button type="submit" loading={enviando}>Gerar novos códigos</Button></div>
        </form>
      )}
      {ativo && (
        <form className="grid gap-3 sm:grid-cols-3" onSubmit={(e) => {
          e.preventDefault();
          run(async () => {
            await apiSend("/auth/mfa/disable", "POST", { password: senha, code: codigo });
            setSenha(""); setCodigo("");
            await s.reload();
            setMsg({ ok: true, texto: "MFA desativado." });
          });
        }}>
          <p className="text-sm text-slate-600 sm:col-span-3">Para desativar, confirme senha e código atual. Se o ambiente exigir MFA, a desativação é bloqueada.</p>
          <Field label="Senha">{(id) => <Input id={id} type="password" required value={senha} onChange={(e) => setSenha(e.target.value)} />}</Field>
          <Field label="Código">{(id) => <Input id={id} inputMode="numeric" maxLength={6} required value={codigo} onChange={(e) => setCodigo(e.target.value.replace(/\D/g, ""))} />}</Field>
          <div className="flex items-end"><Button type="submit" variant="danger" loading={enviando}>Desativar MFA</Button></div>
        </form>
      )}
      {msg && <p className={`mt-3 text-sm ${msg.ok ? "text-emerald-700" : "text-rose-700"}`}>{msg.texto}</p>}
    </Card>
  );
}
