"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { LoadingState } from "@/components/ui";

export default function AdminIndex() {
  const router = useRouter();
  useEffect(() => router.replace("/admin/tenants"), [router]);
  return <LoadingState />;
}
