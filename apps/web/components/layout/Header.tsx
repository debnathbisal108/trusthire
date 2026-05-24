"use client";

import { Bell } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { cn } from "@/lib/utils";

interface Props {
  user: { name?: string; email?: string; role?: string };
}

export default function Header({ user }: Props) {
  const { data: notifications } = useQuery({
    queryKey: ["notifications"],
    queryFn: () => apiClient.notifications.list(),
    refetchInterval: 30_000,
  });

  const unreadCount = notifications?.filter((n) => !n.is_read).length ?? 0;

  return (
    <header className="h-16 flex items-center justify-between px-6 bg-white dark:bg-zinc-900 border-b border-zinc-200 dark:border-zinc-800 flex-shrink-0">
      <div />

      <div className="flex items-center gap-3">
        {/* Notification bell */}
        <button className="relative w-9 h-9 flex items-center justify-center rounded-lg text-zinc-500 hover:text-zinc-900 dark:hover:text-white hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors">
          <Bell className="w-5 h-5" />
          {unreadCount > 0 && (
            <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-red-500" />
          )}
        </button>

        {/* User info */}
        <div className="text-right hidden sm:block">
          <p className="text-sm font-medium text-zinc-900 dark:text-white leading-none">
            {user?.name}
          </p>
          <p className="text-xs text-zinc-400 mt-0.5 capitalize">
            {user?.role?.replace("_", " ")}
          </p>
        </div>
      </div>
    </header>
  );
}
