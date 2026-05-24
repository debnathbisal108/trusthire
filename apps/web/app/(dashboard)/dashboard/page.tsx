import { auth } from "@/lib/auth";
import { Shield, Users, CheckCircle, AlertTriangle } from "lucide-react";
import RecentCandidates from "@/components/dashboard/RecentCandidates";
import FraudAlerts from "@/components/dashboard/FraudAlerts";
import StatsGrid from "@/components/dashboard/StatsGrid";

export default async function DashboardPage() {
  const session = await auth();
  const firstName = session?.user?.name?.split(" ")[0] ?? "there";

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-white">
          Welcome back, {firstName} 👋
        </h1>
        <p className="text-zinc-500 dark:text-zinc-400 mt-1">
          Here's what's happening with your verifications today.
        </p>
      </div>

      {/* Stats */}
      <StatsGrid />

      {/* Main content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <RecentCandidates />
        </div>
        <div>
          <FraudAlerts />
        </div>
      </div>
    </div>
  );
}
