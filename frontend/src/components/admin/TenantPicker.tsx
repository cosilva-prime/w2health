"use client";

import { Select } from "@/components/ui";
import { useApi } from "@/lib/useApi";

export function TenantPicker({ value, onChange, allowAll = false }: {
  value: string | null;
  onChange: (v: string | null) => void;
  allowAll?: boolean;
}) {
  const { data } = useApi<{ itens: { id: string; name: string }[] }>("/admin/tenants");
  return (
    <Select aria-label="Tenant" className="w-64" value={value ?? ""} onChange={(e) => onChange(e.target.value || null)}>
      <option value="">{allowAll ? "Todos os tenants" : "— selecione um tenant —"}</option>
      {(data?.itens ?? []).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
    </Select>
  );
}
