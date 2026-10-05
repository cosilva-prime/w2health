"use client";

/** Configurações FUNCIONAIS do tenant (catálogo fechado do backend). Segredos ficam fora
 * daqui — são write-only na área da plataforma. */

import { useState } from "react";

import { Button, Card, DataState, Input, Select, StatusBadge, Toggle } from "@/components/ui";
import { apiSend, ApiError } from "@/lib/api";
import { LABEL_COMPARACAO } from "@/lib/format";
import { useApi } from "@/lib/useApi";

interface SettingItem {
  key: string;
  label: string;
  description: string;
  category: string;
  value: unknown;
  default: unknown;
  editable: boolean;
  editable_by: "tenant_admin" | "platform";
}

export function SettingsEditor({ base, readOnly = false, onSaved }: {
  base: string;
  readOnly?: boolean;
  onSaved?: () => void;
}) {
  const { data, error, isLoading, reload } = useApi<{ itens: SettingItem[] }>(base);
  const [erro, setErro] = useState<string | null>(null);

  async function salvar(key: string, value: unknown) {
    setErro(null);
    try {
      await apiSend(`${base}/${key}`, "PUT", { value });
      await reload();
      onSaved?.();
    } catch (e) {
      setErro((e as ApiError).message);
    }
  }

  const categorias = Array.from(new Set((data?.itens ?? []).map((i) => i.category)));
  return (
    <Card title="Configurações">
      {erro && <p className="mb-3 rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{erro}</p>}
      <DataState isLoading={isLoading && !data} error={error}>
        <div className="space-y-5">
          {categorias.map((cat) => (
            <div key={cat}>
              <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">{cat}</div>
              <div className="divide-y divide-slate-100 rounded-lg border border-slate-200">
                {data!.itens.filter((i) => i.category === cat).map((i) => (
                  <div key={i.key} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
                    <div className="min-w-0">
                      <div className="text-sm font-medium text-slate-800">{i.label}</div>
                      <div className="text-xs text-slate-500">{i.description}</div>
                      {i.editable_by === "platform" && <StatusBadge tone="gold">definido pela Works2Data</StatusBadge>}
                    </div>
                    <Editor item={i} disabled={readOnly || !i.editable} onSave={(v) => salvar(i.key, v)} />
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </DataState>
    </Card>
  );
}

function Editor({ item, disabled, onSave }: { item: SettingItem; disabled: boolean; onSave: (v: unknown) => void }) {
  const [valor, setValor] = useState(String(item.value));
  if (typeof item.default === "boolean") {
    return <Toggle checked={Boolean(item.value)} disabled={disabled} label={item.label} onChange={(v) => onSave(v)} />;
  }
  if (item.key === "analysis.default_comparison") {
    return (
      <Select value={String(item.value)} disabled={disabled} onChange={(e) => onSave(e.target.value)} className="w-56">
        {Object.entries(LABEL_COMPARACAO).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
      </Select>
    );
  }
  if (typeof item.default === "number") {
    return (
      <div className="flex items-center gap-2">
        <Input type="number" className="w-28" disabled={disabled} value={valor} onChange={(e) => setValor(e.target.value)} />
        {!disabled && <Button size="sm" onClick={() => onSave(Number(valor))}>Salvar</Button>}
      </div>
    );
  }
  return <span className="text-sm text-slate-600">{String(item.value)}</span>;
}
