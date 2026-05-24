"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { signOut } from "next-auth/react";
import {
  LayoutDashboard, Users, Shield, FileText,
  ScrollText, Settings, LogOut,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface NavItem {
  href: string;
  icon: React.ElementType;
  label: string;
  roles?: string[];
}

const NAV: NavItem[] = [
  { href: "/dashboard",   icon: LayoutDashboard, label: "Dashboard"   },
  { href: "/candidates",  icon: Users,           label: "Candidates"  },
  { href: "/compliance",  icon: Shield,          label: "Compliance",
    roles: ["org_admin", "compliance_reviewer", "super_admin"] },
  { href: "/reports",     icon: FileText,        label: "Reports"     },
  { href: "/audit",       icon: ScrollText,      label: "Audit log",
    roles: ["org_admin", "super_admin"] },
];

interface Props {
  user: { name?: string; email?: string; image?: string; role?: string };
}

export default function Sidebar({ user }: Props) {
  const pathname = usePathname();
  const role = user?.role ?? "viewer";

  return (
    <aside className="w-60 flex flex-col bg-white dark:bg-zinc-900 border-r border-zinc-200 dark:border-zinc-800 flex-shrink-0">
      {/* Brand */}
      <div className="h-16 flex items-center px-5 border-b border-zinc-100 dark:border-zinc-800">
        <Shield className="w-5 h-5 text-blue-600 mr-2.5 flex-shrink-0" />
        <span className="font-bold text-zinc-900 dark:text-white">TrustHire AI</span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-3 space-y-0.5 overflow-y-auto">
        {NAV.filter((item) => !item.roles || item.roles.includes(role)).map((item) => {
          const active = pathname === item.href || pathname.startsWith(item.href + "/");
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors",
                active
                  ? "bg-blue-50 dark:bg-blue-950 text-blue-700 dark:text-blue-300 font-medium"
                  : "text-zinc-500 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-white hover:bg-zinc-50 dark:hover:bg-zinc-800"
              )}
            >
              <item.icon className="w-4 h-4 flex-shrink-0" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Bottom */}
      <div className="p-3 border-t border-zinc-100 dark:border-zinc-800 space-y-1">
        <Link
          href="/settings"
          className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-zinc-500 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-white hover:bg-zinc-50 dark:hover:bg-zinc-800 transition-colors"
        >
          <Settings className="w-4 h-4 flex-shrink-0" />
          Settings
        </Link>
        <button
          onClick={() => signOut({ callbackUrl: "/" })}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-zinc-500 dark:text-zinc-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-950 transition-colors"
        >
          <LogOut className="w-4 h-4 flex-shrink-0" />
          Sign out
        </button>

        {/* User avatar */}
        <div className="flex items-center gap-3 px-3 py-2 mt-1">
          {user?.image ? (
            <img src={user.image} alt="" className="w-7 h-7 rounded-full flex-shrink-0" />
          ) : (
            <div className="w-7 h-7 rounded-full bg-blue-100 dark:bg-blue-900 flex items-center justify-center text-xs font-semibold text-blue-700 dark:text-blue-300 flex-shrink-0">
              {user?.name?.[0] ?? "?"}
            </div>
          )}
          <div className="min-w-0">
            <p className="text-xs font-medium text-zinc-900 dark:text-white truncate">
              {user?.name ?? "User"}
            </p>
            <p className="text-xs text-zinc-400 capitalize">
              {role.replace("_", " ")}
            </p>
          </div>
        </div>
      </div>
    </aside>
  );
}
