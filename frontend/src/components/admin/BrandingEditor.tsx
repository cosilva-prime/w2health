"use client";

/**
 * Editor de identidade visual (white-label LIMITADO): nome do produto, 2 cores, textos da
 * tela de login, logo e favicon. Sem CSS/HTML livre. Validações reais no backend
 * (hex, contraste WCAG AA da cor primária, assinatura de imagem PNG/JPEG/WebP ≤ 256 KB).
 */

import { useEffect, useState } from "react";

import { Button, Card, DataState, Field, Input } from "@/components/ui";
import { apiAssetUrl, apiSend, apiUpload, ApiError } from "@/lib/api";
import { Branding } from "@/lib/session";
import { useApi } from "@/lib/useApi";

type Raw = Partial<Record<"product_name" | "primary_color" | "accent_color" | "login_title" | "login_message", string | null>>;

export function BrandingEditor({ base, onSaved }: { base: string; onSaved?: () => void }) {
  const { data, error, isLoading, reload } = useApi<{ raw: Raw; effective: Branding; defaults: Branding }>(base);
  const [form, setForm] = useState<Raw>({});
  const [msg, setMsg] = useState<{ ok: boolean; texto: string } | null>(null);
  const [salvando, setSalvando] = useState(false);

  useEffect(() => {
    if (data) setForm(data.raw);
  }, [data]);

  const set = (k: keyof Raw, v: string) => setForm((f) => ({ ...f, [k]: v }));

  async function salvar() {
    setMsg(null);
    setSalvando(true);
    try {
      const payload: Raw = {};
      for (const [k, v] of Object.entries(form)) payload[k as keyof Raw] = v ? v : null;
      await apiSend(base, "PUT", payload);
      await reload();
      onSaved?.();
      setMsg({ ok: true, texto: "Identidade atualizada." });
    } catch (e) {
      setMsg({ ok: false, texto: (e as ApiError).message });
    } finally {
      setSalvando(false);
    }
  }

  async function enviarImagem(kind: "logo" | "favicon", file: File | undefined) {
    if (!file) return;
    setMsg(null);
    try {
      await apiUpload(`${base}/${kind}`, file);
      await reload();
      onSaved?.();
      setMsg({ ok: true, texto: "Imagem atualizada." });
    } catch (e) {
      setMsg({ ok: false, texto: (e as ApiError).message });
    }
  }

  async function removerImagem(kind: "logo" | "favicon") {
    await apiSend(`${base}/${kind}`, "DELETE");
    await reload();
    onSaved?.();
  }

  const eff = data?.effective;
  const def = data?.defaults;
  return (
    <Card title="Identidade visual">
      <DataState isLoading={isLoading && !data} error={error}>
        {eff && def && (
          <div className="grid gap-6 lg:grid-cols-[1fr_18rem]">
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Nome do produto" hint={`Padrão: ${def.product_name}`}>
                {(id) => <Input id={id} maxLength={60} value={form.product_name ?? ""} placeholder={def.product_name} onChange={(e) => set("product_name", e.target.value)} />}
              </Field>
              <div />
              <Field label="Cor primária" hint="Fundo da navegação — exige contraste com texto branco.">
                {(id) => (
                  <div className="flex gap-2">
                    <input aria-label="Seletor de cor primária" type="color" value={form.primary_color || def.primary_color} onChange={(e) => set("primary_color", e.target.value)} className="h-9 w-12 rounded border border-slate-300" />
                    <Input id={id} maxLength={7} value={form.primary_color ?? ""} placeholder={def.primary_color} onChange={(e) => set("primary_color", e.target.value)} />
                  </div>
                )}
              </Field>
              <Field label="Cor de destaque">
                {(id) => (
                  <div className="flex gap-2">
                    <input aria-label="Seletor de cor de destaque" type="color" value={form.accent_color || def.accent_color} onChange={(e) => set("accent_color", e.target.value)} className="h-9 w-12 rounded border border-slate-300" />
                    <Input id={id} maxLength={7} value={form.accent_color ?? ""} placeholder={def.accent_color} onChange={(e) => set("accent_color", e.target.value)} />
                  </div>
                )}
              </Field>
              <Field label="Título da tela de login">
                {(id) => <Input id={id} maxLength={80} value={form.login_title ?? ""} placeholder={def.login_title} onChange={(e) => set("login_title", e.target.value)} />}
              </Field>
              <Field label="Mensagem da tela de login">
                {(id) => <Input id={id} maxLength={300} value={form.login_message ?? ""} placeholder={def.login_message} onChange={(e) => set("login_message", e.target.value)} />}
              </Field>
              {(["logo", "favicon"] as const).map((kind) => (
                <Field key={kind} label={kind === "logo" ? "Logo" : "Favicon"} hint="PNG, JPEG ou WebP até 256 KB.">
                  {(id) => (
                    <div className="flex items-center gap-2">
                      <input id={id} type="file" accept="image/png,image/jpeg,image/webp" className="text-xs" onChange={(e) => enviarImagem(kind, e.target.files?.[0])} />
                      {eff[`${kind}_url` as "logo_url"] && <Button size="sm" variant="ghost" onClick={() => removerImagem(kind)}>Remover</Button>}
                    </div>
                  )}
                </Field>
              ))}
              <div className="flex items-center gap-3 sm:col-span-2">
                <Button variant="primary" loading={salvando} onClick={salvar}>Salvar</Button>
                <Button variant="ghost" onClick={() => setForm({})}>Voltar ao padrão W2Health</Button>
                {msg && <span className={`text-sm ${msg.ok ? "text-emerald-700" : "text-rose-700"}`}>{msg.texto}</span>}
              </div>
            </div>
            <Preview b={{ ...eff, ...Object.fromEntries(Object.entries(form).filter(([, v]) => v)) } as Branding} />
          </div>
        )}
      </DataState>
    </Card>
  );
}

function Preview({ b }: { b: Branding }) {
  const logo = apiAssetUrl(b.logo_url);
  return (
    <div>
      <div className="mb-1 text-xs font-medium text-slate-500">Pré-visualização</div>
      <div className="overflow-hidden rounded-lg border border-slate-200">
        <div className="flex items-center gap-2 p-3" style={{ backgroundColor: b.primary_color }}>
          {logo ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={logo} alt="" className="h-7 w-7 rounded bg-white object-contain" />
          ) : (
            <div className="grid h-7 w-7 place-items-center rounded text-[10px] font-bold text-brand-900" style={{ backgroundColor: b.accent_color }}>W2</div>
          )}
          <span className="truncate text-xs font-semibold text-white">{b.product_name}</span>
        </div>
        <div className="space-y-1 bg-white p-3">
          <div className="text-sm font-semibold text-slate-800">{b.login_title}</div>
          <div className="text-xs text-slate-500">{b.login_message}</div>
          <span className="inline-block rounded px-2 py-0.5 text-[10px] font-medium text-brand-900" style={{ backgroundColor: b.accent_color }}>destaque</span>
        </div>
      </div>
    </div>
  );
}
