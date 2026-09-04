"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Card, DataState } from "@/components/ui";
import { filtersQuery, useFilters } from "@/lib/filters";
import { fmtBRLCompact, fmtNum } from "@/lib/format";
import { useApi } from "@/lib/useApi";

interface Item {
  id: number;
  codigo: string;
  sexo: string;
  faixa_etaria: string;
  regiao: string;
  plano: string;
  despesa: number;
  eventos: number;
}

export default function BeneficiariosPage() {
  const f = useFilters();
  const router = useRouter();
  const [busca, setBusca] = useState("");
  const [faixa, setFaixa] = useState("");
  const [sexo, setSexo] = useState("");
  const ready = f.competencia != null;

  const extra: Record<string, string> = { page_size: "40" };
  if (faixa) extra.faixa_etaria = faixa;
  if (sexo) extra.sexo = sexo;
  const lista = useApi<{ itens: Item[]; total: number }>(
    ready ? `/analytics/beneficiarios${filtersQuery(f, extra)}` : null,
  );
  const faixas = useApi<{ itens: { id: string }[] }>("/catalogos/faixas-etarias");

  const submitBusca = (e: React.FormEvent) => {
    e.preventDefault();
    const c = busca.trim().toUpperCase();
    if (c) router.push(`/beneficiarios/${c.startsWith("BEN-") ? c : `BEN-${c.padStart(6, "0")}`}`);
  };

  return (
    <div className="space-y-5">
      <Card title="Buscar beneficiário">
        <form onSubmit={submitBusca} className="flex flex-wrap items-center gap-2">
          <input
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            placeholder="BEN-000001 ou 1"
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm"
          />
          <button className="rounded-md bg-brand-600 px-3 py-1.5 text-sm text-white">Abrir</button>
          <span className="mx-2 h-4 w-px bg-slate-200" />
          <select className="rounded-md border border-slate-300 px-2 py-1.5 text-sm" value={faixa} onChange={(e) => setFaixa(e.target.value)}>
            <option value="">Todas as faixas</option>
            {(faixas.data?.itens ?? []).map((x) => (
              <option key={x.id} value={x.id}>{x.id}</option>
            ))}
          </select>
          <select className="rounded-md border border-slate-300 px-2 py-1.5 text-sm" value={sexo} onChange={(e) => setSexo(e.target.value)}>
            <option value="">Ambos os sexos</option>
            <option value="F">F</option>
            <option value="M">M</option>
          </select>
        </form>
      </Card>

      <Card title={`Maiores custos no período (${lista.data?.total ?? 0} beneficiários)`}>
        <DataState isLoading={lista.isLoading && !lista.data} error={lista.error} empty={!lista.data?.itens?.length}>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead>
                <tr className="border-b border-slate-100 text-left text-xs uppercase text-slate-400">
                  <th className="py-2">Beneficiário</th>
                  <th className="py-2">Perfil</th>
                  <th className="py-2">Plano</th>
                  <th className="py-2 text-right">Despesa</th>
                  <th className="py-2 text-right">Eventos</th>
                </tr>
              </thead>
              <tbody>
                {(lista.data?.itens ?? []).map((r) => (
                  <tr key={r.id} className="border-b border-slate-50">
                    <td className="py-2">
                      <Link href={`/beneficiarios/${r.id}`} className="font-mono text-brand-600 hover:underline">
                        {r.codigo}
                      </Link>
                    </td>
                    <td className="py-2 text-slate-500">
                      {r.sexo} · {r.faixa_etaria} · {r.regiao}
                    </td>
                    <td className="py-2 text-slate-500">{r.plano}</td>
                    <td className="py-2 text-right font-medium tabular-nums">{fmtBRLCompact(r.despesa)}</td>
                    <td className="py-2 text-right tabular-nums">{fmtNum(r.eventos)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </DataState>
      </Card>
    </div>
  );
}
