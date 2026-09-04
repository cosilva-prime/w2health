/** Configuração de navegação: itens da sidebar e rótulos para breadcrumbs. */

export interface NavItem {
  href: string;
  label: string;
  /** etapa do backlog em que a tela ganha conteúdo real */
  etapa: number;
}

export const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Visão Executiva", etapa: 6 },
  { href: "/sinistralidade", label: "Sinistralidade", etapa: 6 },
  { href: "/prestadores", label: "Prestadores", etapa: 7 },
  { href: "/beneficiarios", label: "Beneficiários", etapa: 8 },
  { href: "/insights", label: "Insights", etapa: 9 },
  { href: "/configuracao/insights", label: "Configuração", etapa: 11 },
];

const ROTULOS_SEGMENTO: Record<string, string> = {
  configuracao: "Configuração",
};

/** Rótulo legível para um segmento de rota (usado nos breadcrumbs). */
export function segmentLabel(segment: string): string {
  const match = NAV_ITEMS.find((item) => item.href === `/${segment}`);
  if (match) return match.label;
  if (ROTULOS_SEGMENTO[segment]) return ROTULOS_SEGMENTO[segment];
  return segment.charAt(0).toUpperCase() + segment.slice(1);
}
