/**
 * Cliente HTTP mínimo para falar com o backend do W2Health Intelligence.
 * Etapa 1: usado apenas pelo cartão de status (GET /health).
 */

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${path}`;
  let resp: Response;
  try {
    resp = await fetch(url, {
      ...init,
      headers: { Accept: "application/json", ...(init?.headers ?? {}) },
      cache: "no-store",
    });
  } catch {
    throw new ApiError(`Não foi possível conectar ao backend em ${url}`);
  }
  if (!resp.ok) {
    throw new ApiError(`Backend respondeu ${resp.status}`, resp.status);
  }
  return (await resp.json()) as T;
}

export const apiClient = {
  get: <T>(path: string) => request<T>(path, { method: "GET" }),
};

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  environment: string;
  database: string;
  timestamp: string;
}

export const getHealth = () => apiClient.get<HealthResponse>("/health");
