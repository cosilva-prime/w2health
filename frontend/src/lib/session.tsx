"use client";

/**
 * Sessão do usuário (Fundação SaaS V1).
 *
 * Fonte: `GET /api/auth/me` — usuário, tenant ativo, papel, permissões, features, branding
 * e preferências públicas. O frontend usa isso APENAS para adaptar a interface (esconder
 * menu, mostrar estado "recurso não disponível"); o backend continua sendo a autoridade e
 * revalida tudo em cada requisição.
 */

import { useRouter } from "next/navigation";
import {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { mutate as swrMutate } from "swr";

import {
  apiAssetUrl,
  apiGet,
  apiSend,
  refreshSession,
  SESSION_EXPIRED_EVENT,
  setAccessToken,
} from "@/lib/api";

export interface Branding {
  product_name: string;
  primary_color: string;
  accent_color: string;
  login_title: string;
  login_message: string;
  logo_url: string | null;
  favicon_url: string | null;
  customized?: boolean;
}

export interface Me {
  user: { id: string; email: string; name: string; platform_role: string | null; mfa_enabled: boolean };
  memberships: { tenant_id: string; tenant_name: string; role: string; tenant_status: string }[];
  platform_permissions: string[];
  tenant: {
    id: string;
    name: string;
    status: string;
    is_synthetic: boolean;
    plan: { code: string; name: string } | null;
  } | null;
  role: string | null;
  permissions: string[];
  features: string[];
  settings: Record<string, unknown>;
  branding: Branding;
}

export type SessionStatus = "loading" | "authenticated" | "anonymous" | "expired";

interface SessionCtx {
  status: SessionStatus;
  me: Me | null;
  isSuperAdmin: boolean;
  can: (perm: string) => boolean;
  hasFeature: (key: string) => boolean;
  /** Conclui um login: guarda o access token (memória) e carrega /me. */
  acceptToken: (token: string) => Promise<Me | null>;
  reload: () => Promise<Me | null>;
  logout: () => Promise<void>;
  switchTenant: (tenantId: string | null) => Promise<void>;
}

const Ctx = createContext<SessionCtx | null>(null);

const PUBLIC_ROUTES = ["/login"];

export function isPublicRoute(pathname: string): boolean {
  return PUBLIC_ROUTES.some((r) => pathname === r || pathname.startsWith(`${r}/`));
}

/** Aplica a identidade visual do tenant como variáveis CSS (sem CSS arbitrário). */
export function applyBranding(b: Branding | null | undefined): void {
  if (typeof document === "undefined" || !b) return;
  const root = document.documentElement;
  const hex = /^#[0-9a-fA-F]{6}$/;
  root.style.setProperty("--w2-primary", hex.test(b.primary_color) ? b.primary_color : "#0b1b32");
  root.style.setProperty("--w2-accent", hex.test(b.accent_color) ? b.accent_color : "#d3a63e");
  document.title = b.product_name || "W2Health Intelligence";
  // favicon do tenant (imagem já validada pelo backend); sem ele, o ícone padrão W2Health
  const link = document.querySelector<HTMLLinkElement>("link[rel='icon']");
  const fav = b.favicon_url ? apiAssetUrl(b.favicon_url) : null;
  if (link) {
    if (!link.dataset.w2Default) link.dataset.w2Default = link.href;
    link.href = fav ?? link.dataset.w2Default;
  }
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<SessionStatus>("loading");
  const [me, setMe] = useState<Me | null>(null);
  const router = useRouter();

  const reload = useCallback(async (): Promise<Me | null> => {
    try {
      const m = await apiGet<Me>("/auth/me");
      setMe(m);
      setStatus("authenticated");
      applyBranding(m.branding);
      return m;
    } catch {
      setMe(null);
      setStatus("anonymous");
      return null;
    }
  }, []);

  // Restaura a sessão pelo cookie de refresh ao carregar a aplicação.
  useEffect(() => {
    let vivo = true;
    (async () => {
      const ok = await refreshSession();
      if (!vivo) return;
      if (ok) await reload();
      else setStatus("anonymous");
    })();
    return () => {
      vivo = false;
    };
  }, [reload]);

  useEffect(() => {
    const onExpired = () => {
      setAccessToken(null);
      setStatus((s) => (s === "authenticated" ? "expired" : s));
    };
    window.addEventListener(SESSION_EXPIRED_EVENT, onExpired);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, onExpired);
  }, []);

  const acceptToken = useCallback(
    async (token: string) => {
      setAccessToken(token);
      return reload();
    },
    [reload],
  );

  const logout = useCallback(async () => {
    try {
      await apiSend("/auth/logout", "POST");
    } catch {
      /* sessão já encerrada */
    }
    setAccessToken(null);
    setMe(null);
    setStatus("anonymous");
    await swrMutate(() => true, undefined, { revalidate: false });
    router.replace("/login");
  }, [router]);

  const switchTenant = useCallback(
    async (tenantId: string | null) => {
      const r = await apiSend<{ access_token: string }>("/auth/switch-tenant", "POST", {
        tenant_id: tenantId,
      });
      setAccessToken(r.access_token);
      // nenhum dado do tenant anterior pode permanecer em cache
      await swrMutate(() => true, undefined, { revalidate: false });
      await reload();
      router.replace(tenantId ? "/" : "/admin/tenants");
    },
    [reload, router],
  );

  const value = useMemo<SessionCtx>(() => {
    const perms = new Set(me?.permissions ?? []);
    const feats = new Set(me?.features ?? []);
    return {
      status,
      me,
      isSuperAdmin: me?.user.platform_role === "SUPER_ADMIN",
      can: (p) => perms.has(p) || (me?.platform_permissions ?? []).includes(p),
      hasFeature: (k) => feats.has(k),
      acceptToken,
      reload,
      logout,
      switchTenant,
    };
  }, [status, me, acceptToken, reload, logout, switchTenant]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useSession(): SessionCtx {
  const c = useContext(Ctx);
  if (!c) throw new Error("useSession fora do SessionProvider");
  return c;
}

export const ROLE_LABEL: Record<string, string> = {
  SUPER_ADMIN: "Works2Data",
  TENANT_ADMIN: "Administrador",
  MANAGER: "Gestor",
  VIEWER: "Leitor",
};
