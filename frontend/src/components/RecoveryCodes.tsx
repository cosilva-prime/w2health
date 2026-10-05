"use client";

import { useState } from "react";

import { Button } from "@/components/ui";

/**
 * Exibe os códigos de recuperação UMA única vez (o servidor só guarda o hash).
 * Nada é persistido no navegador.
 */
export function RecoveryCodes({ codes, onDone, doneLabel = "Já guardei os códigos" }: {
  codes: string[];
  onDone: () => void;
  doneLabel?: string;
}) {
  const [copiado, setCopiado] = useState(false);
  return (
    <div className="space-y-3 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm">
      <p className="font-medium text-amber-900">Guarde estes códigos de recuperação em local seguro.</p>
      <p className="text-xs text-amber-800">
        Cada código vale uma única vez, caso você perca o acesso ao autenticador. Eles não serão exibidos novamente;
        gerar novos códigos invalida estes.
      </p>
      <ul className="grid grid-cols-2 gap-1 font-mono text-sm">
        {codes.map((c) => <li key={c} className="rounded bg-white px-2 py-1 text-center">{c}</li>)}
      </ul>
      <div className="flex flex-wrap gap-2">
        <Button type="button" size="sm" onClick={async () => {
          try {
            await navigator.clipboard.writeText(codes.join("\n"));
            setCopiado(true);
          } catch {
            setCopiado(false);
          }
        }}>{copiado ? "Copiado" : "Copiar"}</Button>
        <Button type="button" size="sm" variant="primary" onClick={onDone}>{doneLabel}</Button>
      </div>
    </div>
  );
}
