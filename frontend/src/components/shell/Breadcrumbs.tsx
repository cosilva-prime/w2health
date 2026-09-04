"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Fragment } from "react";

import { segmentLabel } from "@/lib/nav";

export function Breadcrumbs() {
  const pathname = usePathname();
  const segments = pathname.split("/").filter(Boolean);

  const crumbs = [
    { href: "/", label: "Início" },
    ...segments.map((segment, index) => ({
      href: "/" + segments.slice(0, index + 1).join("/"),
      label: segmentLabel(segment),
    })),
  ];

  return (
    <nav aria-label="breadcrumb" className="flex items-center gap-1.5 text-xs text-slate-500">
      {crumbs.map((crumb, index) => {
        const last = index === crumbs.length - 1;
        return (
          <Fragment key={crumb.href}>
            {index > 0 && <span aria-hidden>/</span>}
            {last ? (
              <span className="font-medium text-slate-700">{crumb.label}</span>
            ) : (
              <Link href={crumb.href} className="hover:text-brand-600 hover:underline">
                {crumb.label}
              </Link>
            )}
          </Fragment>
        );
      })}
    </nav>
  );
}
