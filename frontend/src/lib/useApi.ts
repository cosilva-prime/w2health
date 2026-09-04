"use client";

import useSWR from "swr";

import { apiGet } from "@/lib/api";

/** Hook de leitura da API (SWR). `path=null` desabilita a chamada. */
export function useApi<T = unknown>(path: string | null) {
  const { data, error, isLoading, mutate } = useSWR<T>(
    path,
    (p: string) => apiGet<T>(p),
    { revalidateOnFocus: false, keepPreviousData: true },
  );
  return { data, error: error as Error | undefined, isLoading, reload: mutate };
}
