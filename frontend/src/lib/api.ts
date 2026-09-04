/** Cliente da API do W2Health Intelligence. */

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8010/api";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function apiGet<T = unknown>(path: string): Promise<T> {
  let resp: Response;
  try {
    resp = await fetch(`${API_BASE_URL}${path}`, {
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
  } catch {
    throw new ApiError(`Não foi possível conectar ao backend (${API_BASE_URL})`);
  }
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`;
    try {
      const j = await resp.json();
      if (j?.detail) detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch {
      /* ignore */
    }
    throw new ApiError(detail, resp.status);
  }
  return (await resp.json()) as T;
}

/** POST/PUT/DELETE com corpo JSON — usado só pela tela de Configuração (v1.1, Etapa C). */
export async function apiSend<T = unknown>(
  path: string,
  method: "POST" | "PUT" | "DELETE",
  body?: unknown,
): Promise<T> {
  let resp: Response;
  try {
    resp = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(`Não foi possível conectar ao backend (${API_BASE_URL})`);
  }
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`;
    try {
      const j = await resp.json();
      if (j?.detail) detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch {
      /* ignore */
    }
    throw new ApiError(detail, resp.status);
  }
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

export const qs = (params: Record<string, string | number | null | undefined>): string => {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v != null && v !== "") p.set(k, String(v));
  const s = p.toString();
  return s ? `?${s}` : "";
};

// ------------------------------------------------------------------- tipos parciais
export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  environment: string;
  database: string;
  timestamp: string;
}

export interface Bridge {
  delta_total: number;
  efeito_frequencia: number;
  efeito_custo_medio: number;
  interacao: number;
  metodo: string;
  efeito_principal: "frequencia" | "custo_medio" | "misto";
  qtd_anterior: number;
  qtd_atual: number;
  custo_medio_anterior: number;
  custo_medio_atual: number;
  variacao_frequencia_pct: number | null;
  variacao_custo_medio_pct: number | null;
}

export interface Fator {
  chave: string;
  categoria: string;
  despesa_anterior: number;
  despesa_atual: number;
  impacto_financeiro: number;
  impacto_pp: number;
  efeito_principal: "frequencia" | "custo_medio" | "misto";
  participacao_variacao: number;
  bridge: Bridge;
}

export interface Insight {
  id: string;
  tipo: string;
  severidade: string;
  emoji: string;
  titulo: string;
  descricao: string;
  metricas: Record<string, unknown>;
  deep_link: { rota: string; params: Record<string, string> };
  score: number;
  metodologia: string;
}

export const insightHref = (i: Insight): string => {
  const p = new URLSearchParams(i.deep_link.params as Record<string, string>);
  const s = p.toString();
  return `${i.deep_link.rota}${s ? `?${s}` : ""}`;
};
