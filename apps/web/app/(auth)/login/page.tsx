import { auth, signIn } from "@/lib/auth";
import { redirect } from "next/navigation";
import { Shield } from "lucide-react";

export default async function LoginPage({
  searchParams,
}: {
  searchParams: { callbackUrl?: string; error?: string };
}) {
  const session = await auth();
  if (session) redirect(searchParams.callbackUrl ?? "/dashboard");

  const error = searchParams.error;

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950 flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        {/* Card */}
        <div className="bg-white dark:bg-zinc-900 rounded-2xl border border-zinc-200 dark:border-zinc-800 p-8 shadow-sm">
          {/* Logo */}
          <div className="flex flex-col items-center mb-8">
            <div className="w-12 h-12 rounded-2xl bg-blue-600 flex items-center justify-center mb-4">
              <Shield className="w-6 h-6 text-white" />
            </div>
            <h1 className="text-xl font-bold text-zinc-900 dark:text-white">
              TrustHire AI
            </h1>
            <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">
              Sign in to your workspace
            </p>
          </div>

          {/* Error */}
          {error && (
            <div className="mb-4 p-3 rounded-lg bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 text-sm text-red-700 dark:text-red-300">
              {error === "OAuthAccountNotLinked"
                ? "This email is already linked to a different sign-in method."
                : "Sign-in failed. Please try again."}
            </div>
          )}

          {/* Google Sign-In */}
          <form
            action={async () => {
              "use server";
              await signIn("google", {
                redirectTo: searchParams.callbackUrl ?? "/dashboard",
              });
            }}
          >
            <button
              type="submit"
              className="w-full flex items-center justify-center gap-3 px-4 py-3 text-sm font-medium bg-white dark:bg-zinc-800 text-zinc-900 dark:text-white border border-zinc-200 dark:border-zinc-700 rounded-xl hover:bg-zinc-50 dark:hover:bg-zinc-700 transition-colors shadow-sm"
            >
              <svg viewBox="0 0 24 24" className="w-5 h-5 flex-shrink-0" aria-hidden>
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
              </svg>
              Continue with Google
            </button>
          </form>

          <p className="mt-6 text-center text-xs text-zinc-400">
            By signing in you agree to our{" "}
            <a href="/terms" className="underline hover:text-zinc-600">
              Terms
            </a>{" "}
            and{" "}
            <a href="/privacy" className="underline hover:text-zinc-600">
              Privacy Policy
            </a>
          </p>
        </div>

        <p className="text-center text-xs text-zinc-400 mt-6">
          TrustHire AI · GDPR & DPDP compliant
        </p>
      </div>
    </div>
  );
}
