"use client";

import { useState } from "react";

import { Badge, Card, DataState } from "@/components/ui";
import { apiSend } from "@/lib/api";
import { corSeveridade } from "@/lib/format";
import { useApi } from "@/lib/useApi";

interface IndicadorDef {
  chave: string;
  rotulo: string;
  unidade: string;
  descricao: string;
}
interface Regra {
  id: number;
  nome: string;
  entidade: string;
  indicador: string;
  operador: string;
  limite: number;
  severidade: string;
  ativo: boolean;
}

const ENTIDADE_LABEL: Record<string, string> = {
  beneficiario: "Beneficiário",
  prestador: "Prestador",
  procedimento: "Procedimento",
  plano: "Plano",
  contrato: "Contrato",
  financeiro: "Financeiro (glosa/coparticipação)",
};
const SEVERIDADE_OPCOES = [
  ["critica", "Crítica"],
  ["atencao", "Atenção"],
  ["informativo", "Informativo"],
] as const;
const OPERADOR_OPCOES = [">=", ">", "<=", "<", "=="] as const;

const FORM_VAZIO = {
  id: null as number | null,
  nome: "",
  entidade: "beneficiario",
  indicador: "",
  operador: ">=" as string,
  limite: "",
  severidade: "atencao" as string,
  ativo: true,
};

export default function ConfiguracaoInsightsPage() {
  const catalogo = useApi<{ itens: Record<string, IndicadorDef[]> }>("/config/indicadores");
  const regras = useApi<Regra[]>("/config/regras-alerta");
  const [form, setForm] = useState(FORM_VAZIO);
  const [erro, setErro] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);

  const indicadoresDaEntidade = catalogo.data?.itens[form.entidade] ?? [];

  const editar = (r: Regra) => {
    setForm({
      id: r.id, nome: r.nome, entidade: r.entidade, indicador: r.indicador,
      operador: r.operador, limite: String(r.limite), severidade: r.severidade, ativo: r.ativo,
    });
    setErro(null);
  };

  const cancelar = () => setForm(FORM_VAZIO);

  const alternarAtivo = async (r: Regra) => {
    await apiSend(`/config/regras-alerta/${r.id}`, "PUT", { ativo: !r.ativo });
    regras.reload();
  };

  const excluir = async (r: Regra) => {
    if (!confirm(`Excluir a regra "${r.nome}"?`)) return;
    await apiSend(`/config/regras-alerta/${r.id}`, "DELETE");
    regras.reload();
  };

  const salvar = async (e: React.FormEvent) => {
    e.preventDefault();
    setErro(null);
    const limite = Number(form.limite);
    if (!form.nome.trim() || !form.indicador || Number.isNaN(limite)) {
      setErro("Preencha nome, indicador e um limite numérico válido.");
      return;
    }
    setSalvando(true);
    try {
      const payload = {
        nome: form.nome, entidade: form.entidade, indicador: form.indicador,
        operador: form.operador, limite, severidade: form.severidade, ativo: form.ativo,
      };
      if (form.id) {
        await apiSend(`/config/regras-alerta/${form.id}`, "PUT", payload);
      } else {
        await apiSend("/config/regras-alerta", "POST", payload);
      }
      setForm(FORM_VAZIO);
      regras.reload();
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Erro ao salvar a regra.");
    } finally {
      setSalvando(false);
    }
  };

  return (
    <div className="space-y-5">
      <Card title="O que é uma regra de alerta?">
        <p className="text-sm text-slate-600">
          Um <b>Alerta configurado</b> é diferente de um <b>Insight automático</b>: o insight é
          uma descoberta do motor, sempre calculada; o alerta só existe se você definir uma
          regra aqui. A regra é avaliada contra os dados reais/sintéticos do período — só
          dispara quando o indicador realmente cruza o limite.
        </p>
      </Card>

      <Card title={form.id ? `Editando regra #${form.id}` : "Nova regra de alerta"}>
        <form onSubmit={salvar} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <label className="flex flex-col gap-1 text-xs text-slate-500">
            Nome
            <input
              className="rounded-md border border-slate-300 px-2 py-1.5 text-sm"
              value={form.nome}
              onChange={(e) => setForm((f) => ({ ...f, nome: e.target.value }))}
              placeholder="Ex.: Beneficiário de alto impacto"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-slate-500">
            Entidade
            <select
              className="rounded-md border border-slate-300 px-2 py-1.5 text-sm"
              value={form.entidade}
              onChange={(e) => setForm((f) => ({ ...f, entidade: e.target.value, indicador: "" }))}
            >
              {Object.keys(ENTIDADE_LABEL).map((k) => (
                <option key={k} value={k}>{ENTIDADE_LABEL[k]}</option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs text-slate-500">
            Indicador
            <select
              className="rounded-md border border-slate-300 px-2 py-1.5 text-sm"
              value={form.indicador}
              onChange={(e) => setForm((f) => ({ ...f, indicador: e.target.value }))}
            >
              <option value="">Selecione…</option>
              {indicadoresDaEntidade.map((i) => (
                <option key={i.chave} value={i.chave}>{i.rotulo} ({i.unidade})</option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs text-slate-500">
            Operador
            <select
              className="rounded-md border border-slate-300 px-2 py-1.5 text-sm"
              value={form.operador}
              onChange={(e) => setForm((f) => ({ ...f, operador: e.target.value }))}
            >
              {OPERADOR_OPCOES.map((o) => <option key={o} value={o}>{o}</option>)}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs text-slate-500">
            Limite
            <input
              type="number" step="any"
              className="rounded-md border border-slate-300 px-2 py-1.5 text-sm"
              value={form.limite}
              onChange={(e) => setForm((f) => ({ ...f, limite: e.target.value }))}
              placeholder="Ex.: 50"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-slate-500">
            Severidade
            <select
              className="rounded-md border border-slate-300 px-2 py-1.5 text-sm"
              value={form.severidade}
              onChange={(e) => setForm((f) => ({ ...f, severidade: e.target.value }))}
            >
              {SEVERIDADE_OPCOES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
            </select>
          </label>
          <label className="flex items-center gap-2 text-xs text-slate-500">
            <input
              type="checkbox"
              checked={form.ativo}
              onChange={(e) => setForm((f) => ({ ...f, ativo: e.target.checked }))}
            />
            Ativa
          </label>

          <div className="col-span-full flex items-center gap-2">
            <button
              type="submit"
              disabled={salvando}
              className="rounded-md bg-brand-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
            >
              {form.id ? "Salvar alterações" : "Criar regra"}
            </button>
            {form.id && (
              <button type="button" onClick={cancelar} className="rounded-md border border-slate-300 px-3 py-1.5 text-sm">
                Cancelar edição
              </button>
            )}
            {erro && <span className="text-xs text-rose-600">{erro}</span>}
          </div>
        </form>
      </Card>

      <Card title={`Regras cadastradas (${regras.data?.length ?? 0})`}>
        <DataState isLoading={regras.isLoading && !regras.data} error={regras.error} empty={!regras.data?.length}>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-sm">
              <thead>
                <tr className="border-b border-slate-100 text-left text-xs uppercase text-slate-400">
                  <th className="py-2">Nome</th>
                  <th className="py-2">Entidade</th>
                  <th className="py-2">Indicador</th>
                  <th className="py-2">Condição</th>
                  <th className="py-2">Severidade</th>
                  <th className="py-2">Ativa</th>
                  <th className="py-2" />
                </tr>
              </thead>
              <tbody>
                {(regras.data ?? []).map((r) => (
                  <tr key={r.id} className="border-b border-slate-50">
                    <td className="py-2">{r.nome}</td>
                    <td className="py-2 text-slate-500">{ENTIDADE_LABEL[r.entidade] ?? r.entidade}</td>
                    <td className="py-2 text-slate-500">{r.indicador}</td>
                    <td className="py-2 font-mono text-xs text-slate-600">{r.operador} {r.limite}</td>
                    <td className="py-2">
                      <Badge className={corSeveridade(r.severidade === "critica" ? "alta" : r.severidade === "atencao" ? "media" : "info")}>
                        {r.severidade}
                      </Badge>
                    </td>
                    <td className="py-2">
                      <button
                        onClick={() => alternarAtivo(r)}
                        className={`rounded-full px-2 py-0.5 text-xs ${r.ativo ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-500"}`}
                      >
                        {r.ativo ? "sim" : "não"}
                      </button>
                    </td>
                    <td className="py-2 text-right">
                      <button onClick={() => editar(r)} className="mr-2 text-xs text-brand-600 hover:underline">editar</button>
                      <button onClick={() => excluir(r)} className="text-xs text-rose-600 hover:underline">excluir</button>
                    </td>
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
