"use client";

import { BrandingEditor } from "@/components/admin/BrandingEditor";
import { PageHeader } from "@/components/ui";
import { useSession } from "@/lib/session";

export default function GestaoIdentidadePage() {
  const s = useSession();
  return (
    <div className="space-y-4">
      <PageHeader title="Identidade visual" description="Personalização limitada e segura: nome, cores, textos de login e logo." />
      <BrandingEditor base="/tenant/branding" onSaved={() => s.reload()} />
    </div>
  );
}
