"use client";

/**
 * Login — e-mail/senha → (código MFA | troca obrigatória de senha | configuração de MFA).
 *
 * - Branding público por `?tenant=<código>` (código desconhecido = identidade padrão; o
 *   backend não revela se o tenant existe).
 * - `next` só aceita caminho relativo interno (evita open redirect).
 * - Nenhuma credencial/segredo é guardado no navegador; o access token fica em memória.
 */

import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, ReactNode, useEffect, useState } from "react";

import { Button, Field, Input } from "@/components/ui";
import { apiAssetUrl, apiGet, apiSend, ApiError } from "@/lib/api";
import { applyBranding, Branding, useSession } from "@/lib/session";

type Etapa =
  | { tipo: "credenciais" }
  | { tipo: "mfa"; challenge: string }
  | { tipo: "troca_senha"; challenge: string }
  | { tipo: "configurar_mfa"; challenge: string; setup?: { qr_svg: string; secret: string } };

interface LoginResp {
  status: "ok" | "mfa_required" | "password_change_required" | "mfa_setup_required";
  access_token?: string;
  challenge_token?: string;
}

function destinoSeguro(next: string | null): string | null {
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.startsWith("/login")) return null;
  return next;
}

export default function LoginPage() {
  const params = useSearchParams();
  const router = useRouter();
  const s = useSession();
  const [branding, setBranding] = useState<Branding | null>(null);
  const [etapa, setEtapa] = useState<Etapa>({ tipo: "credenciais" });
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [codigo, setCodigo] = useState("");
  const [novaSenha, setNovaSenha] = useState("");
  const [confirmacao, setConfirmacao] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const tenant = params.get("tenant");

  useEffect(() => {
    apiGet<Branding>(`/public/branding${tenant ? `?tenant=${encodeURIComponent(tenant)}` : ""}`)
      .then((b) => {
        setBranding(b);
        applyBranding(b);
      })
      .catch(() => setBranding(null));
  }, [tenant]);

  // já autenticado (ex.: voltou para /login) → segue para o produto
  useEffect(() => {
    if (s.status === "authenticated" && s.me) router.replace(destinoSeguro(params.get("next")) ?? "/");
  }, [s.status, s.me, router, params]);

  async function concluir(r: LoginResp) {
    setCodigo("");
    if (r.status === "ok" && r.access_token) {
      const me = await s.acceptToken(r.access_token);
      const padrao = me && !me.tenant && me.user.platform_role === "SUPER_ADMIN" ? "/admin/tenants" : "/";
      router.replace(destinoSeguro(params.get("next")) ?? padrao);
      return;
    }
    const chall = r.challenge_token ?? "";
    if (r.status === "mfa_required") setEtapa({ tipo: "mfa", challenge: chall });
    else if (r.status === "password_change_required") setEtapa({ tipo: "troca_senha", challenge: chall });
    else if (r.status === "mfa_setup_required") {
      const setup = await apiSend<{ qr_svg: string; secret: string }>("/auth/mfa/setup", "POST", {
        challenge_token: chall,
      });
      setEtapa({ tipo: "configurar_mfa", challenge: chall, setup });
    }
  }

  async function executar(fn: () => Promise<void>) {
    setErro(null);
    setEnviando(true);
    try {
      await fn();
    } catch (e) {
      const err = e as ApiError;
      if (err.code === "session_expired") setEtapa({ tipo: "credenciais" });
      setErro(err.message);
    } finally {
      setEnviando(false);
    }
  }

  const onCredenciais = (e: FormEvent) => {
    e.preventDefault();
    executar(async () => {
      const r = await apiSend<LoginResp>("/auth/login", "POST", {
        email, password: senha, ...(tenant ? { tenant } : {}),
      });
      setSenha("");
      await concluir(r);
    });
  };

  const onMfa = (e: FormEvent) => {
    e.preventDefault();
    if (etapa.tipo !== "mfa") return;
    executar(async () => {
      await concluir(await apiSend<LoginResp>("/auth/mfa/verify", "POST", {
        challenge_token: etapa.challenge, code: codigo,
      }));
    });
  };

  const onTrocaSenha = (e: FormEvent) => {
    e.preventDefault();
    if (etapa.tipo !== "troca_senha") return;
    if (novaSenha !== confirmacao) {
      setErro("As senhas não conferem.");
      return;
    }
    executar(async () => {
      const r = await apiSend<LoginResp>("/auth/password/required-change", "POST", {
        challenge_token: etapa.challenge, new_password: novaSenha,
      });
      setNovaSenha("");
      setConfirmacao("");
      await concluir(r);
    });
  };

  const onConfirmarMfa = (e: FormEvent) => {
    e.preventDefault();
    if (etapa.tipo !== "configurar_mfa") return;
    executar(async () => {
      await concluir(await apiSend<LoginResp>("/auth/mfa/confirm", "POST", {
        challenge_token: etapa.challenge, code: codigo,
      }));
    });
  };

  const logo = apiAssetUrl(branding?.logo_url);

  return (
    <div className="grid min-h-screen bg-slate-100 lg:grid-cols-2">
      <div className="hidden flex-col justify-between bg-tenant-primary p-10 text-white lg:flex">
        <div className="flex items-center gap-3">
          {logo ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={logo} alt="" className="h-10 w-10 rounded-lg bg-white object-contain p-0.5" />
          ) : (
            <div className="grid h-10 w-10 place-items-center rounded-lg bg-tenant-accent font-bold text-brand-900">W2</div>
          )}
          <span className="text-lg font-semibold">{branding?.product_name ?? "W2Health Intelligence"}</span>
        </div>
        <div>
          <h1 className="text-3xl font-semibold leading-tight">{branding?.login_title ?? "W2Health Intelligence"}</h1>
          <p className="mt-3 max-w-md text-slate-300">
            {branding?.login_message ?? "Decision Intelligence Platform for Healthcare"}
          </p>
        </div>
        <p className="text-xs text-slate-400">Um produto Works2Data · Acesso restrito a usuários autorizados.</p>
      </div>

      <div className="flex items-center justify-center p-6">
        <div className="w-full max-w-sm rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          {etapa.tipo === "credenciais" && (
            <Form titulo="Entrar" onSubmit={onCredenciais} erro={erro}>
              <Field label="E-mail">
                {(id) => <Input id={id} type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />}
              </Field>
              <Field label="Senha">
                {(id) => <Input id={id} type="password" autoComplete="current-password" required value={senha} onChange={(e) => setSenha(e.target.value)} />}
              </Field>
              <Button variant="primary" type="submit" loading={enviando} className="w-full">Entrar</Button>
            </Form>
          )}

          {etapa.tipo === "mfa" && (
            <Form titulo="Verificação em duas etapas" onSubmit={onMfa} erro={erro}
              subtitulo="Informe o código de 6 dígitos do seu aplicativo autenticador.">
              <CodigoInput value={codigo} onChange={setCodigo} />
              <Button variant="primary" type="submit" loading={enviando} className="w-full">Verificar</Button>
              <Voltar onClick={() => setEtapa({ tipo: "credenciais" })} />
            </Form>
          )}

          {etapa.tipo === "troca_senha" && (
            <Form titulo="Defina uma nova senha" onSubmit={onTrocaSenha} erro={erro}
              subtitulo="Por segurança, troque a senha temporária antes de continuar.">
              <Field label="Nova senha" hint="Mínimo de 12 caracteres; evite sequências previsíveis.">
                {(id) => <Input id={id} type="password" autoComplete="new-password" required value={novaSenha} onChange={(e) => setNovaSenha(e.target.value)} />}
              </Field>
              <Field label="Confirme a nova senha">
                {(id) => <Input id={id} type="password" autoComplete="new-password" required value={confirmacao} onChange={(e) => setConfirmacao(e.target.value)} />}
              </Field>
              <Button variant="primary" type="submit" loading={enviando} className="w-full">Salvar e continuar</Button>
            </Form>
          )}

          {etapa.tipo === "configurar_mfa" && (
            <Form titulo="Configure a autenticação em dois fatores" onSubmit={onConfirmarMfa} erro={erro}
              subtitulo="Este acesso exige MFA. Escaneie o QR Code com um aplicativo autenticador (ex.: Google Authenticator, Microsoft Authenticator) e informe o código gerado.">
              {etapa.setup && (
                <div className="space-y-2 text-center">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={etapa.setup.qr_svg} alt="QR Code para o aplicativo autenticador" className="mx-auto h-44 w-44" />
                  <details className="text-xs text-slate-500">
                    <summary className="cursor-pointer">Não consegue escanear? Digite a chave</summary>
                    <code className="mt-1 block break-all rounded bg-slate-50 p-2 font-mono">{etapa.setup.secret}</code>
                  </details>
                </div>
              )}
              <CodigoInput value={codigo} onChange={setCodigo} />
              <Button variant="primary" type="submit" loading={enviando} className="w-full">Ativar e entrar</Button>
            </Form>
          )}
        </div>
      </div>
    </div>
  );
}

function Form({ titulo, subtitulo, erro, onSubmit, children }: {
  titulo: string;
  subtitulo?: string;
  erro: string | null;
  onSubmit: (e: FormEvent) => void;
  children: ReactNode;
}) {
  return (
    <form onSubmit={onSubmit} className="space-y-4" noValidate={false}>
      <div>
        <h2 className="text-lg font-semibold text-slate-900">{titulo}</h2>
        {subtitulo && <p className="mt-1 text-sm text-slate-500">{subtitulo}</p>}
      </div>
      {erro && <div role="alert" className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{erro}</div>}
      {children}
    </form>
  );
}

function CodigoInput({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <Field label="Código de 6 dígitos">
      {(id) => (
        <Input id={id} inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" maxLength={6} required
          value={value} onChange={(e) => onChange(e.target.value.replace(/\D/g, ""))}
          className="text-center font-mono text-lg tracking-[0.4em]" />
      )}
    </Field>
  );
}

function Voltar({ onClick }: { onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} className="w-full text-center text-xs text-slate-500 hover:underline">
      Voltar
    </button>
  );
}
