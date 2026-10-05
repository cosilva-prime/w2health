"use client";

import { UsersPanel } from "@/components/admin/UsersPanel";
import { PageHeader } from "@/components/ui";
import { useSession } from "@/lib/session";

export default function GestaoUsuariosPage() {
  const s = useSession();
  return (
    <div className="space-y-4">
      <PageHeader
        title="Usuários do ambiente"
        description="Administradores gerenciam usuários apenas deste ambiente. Contas compartilhadas com outros ambientes e o papel Works2Data são geridos pela plataforma."
      />
      <UsersPanel base="/tenant" resetBase="/tenant/users" currentUserId={s.me?.user.id}
        canManage={s.can("tenant_users:manage")} />
    </div>
  );
}
