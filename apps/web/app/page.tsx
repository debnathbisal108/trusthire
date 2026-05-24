import { auth, signIn } from "@/lib/auth";
import { redirect } from "next/navigation";
import { Shield, CheckCircle, Phone, Mail, FileText, BarChart3, Lock, Zap } from "lucide-react";

export default async function LandingPage() {
  const session = await auth();
  if (session) redirect("/dashboard");

  return (
    <div className="min-h-screen bg-white dark:bg-zinc-950">
      {/* Nav */}
      <nav className="sticky top-0 z-50 border-b border-zinc-100 dark:border-zinc-800 bg-white/95 dark:bg-zinc-950/95 backdrop-blur">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <Shield className="w-6 h-6 text-blue-600" />
            <span className="font-bold text-lg tracking-tight">TrustHire AI</span>
          </div>
          <form
            action={async () => {
              "use server";
              await signIn("google", { redirectTo: "/dashboard" });
            }}
          >
            <button
              type="submit"
              className="px-4 py-2 text-sm font-medium bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              Get started
            </button>
          </form>
        </div>
      </nav>

      {/* Hero */}
      <section className="max-w-4xl mx-auto px-6 pt-24 pb-20 text-center">
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-blue-50 dark:bg-blue-950 text-blue-700 dark:text-blue-300 text-sm font-medium mb-8">
          <Zap className="w-3.5 h-3.5" />
          AI-powered · GDPR compliant · Open-source stack
        </div>

        <h1 className="text-5xl sm:text-6xl font-bold tracking-tight text-zinc-900 dark:text-white mb-6 leading-tight">
          Background verification
          <br />
          <span className="text-blue-600">that actually works</span>
        </h1>

        <p className="text-xl text-zinc-500 dark:text-zinc-400 mb-10 max-w-2xl mx-auto leading-relaxed">
          TrustHire AI autonomously verifies employment history, education credentials,
          and public records using AI voice calls and email automation — with full audit
          trails and legal compliance.
        </p>

        {/* Google Sign-In */}
        <div className="flex flex-col items-center gap-4">
          <form
            action={async () => {
              "use server";
              await signIn("google", { redirectTo: "/dashboard" });
            }}
          >
            <button
              type="submit"
              className="flex items-center gap-3 px-6 py-3 text-base font-medium bg-white dark:bg-zinc-800 text-zinc-900 dark:text-white border border-zinc-200 dark:border-zinc-700 rounded-xl shadow-sm hover:bg-zinc-50 dark:hover:bg-zinc-700 transition-colors"
            >
              <GoogleIcon />
              Continue with Google
            </button>
          </form>
          <p className="text-sm text-zinc-400">
            Free to start · No credit card required
          </p>
        </div>
      </section>

      {/* Tech stack logos */}
      <section className="border-y border-zinc-100 dark:border-zinc-800 py-10">
        <div className="max-w-4xl mx-auto px-6">
          <p className="text-center text-xs font-medium tracking-widest text-zinc-400 uppercase mb-6">
            Built on enterprise open source
          </p>
          <div className="flex flex-wrap justify-center gap-6 text-zinc-400 text-sm font-medium">
            {["Llama 3 · Ollama", "PostgreSQL", "Qdrant", "Celery", "Piper TTS", "Whisper STT", "Next.js 15"].map(
              (t) => (
                <span key={t} className="opacity-60">
                  {t}
                </span>
              )
            )}
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="max-w-6xl mx-auto px-6 py-24">
        <div className="text-center mb-14">
          <h2 className="text-3xl font-bold text-zinc-900 dark:text-white mb-3">
            Everything you need to verify candidates
          </h2>
          <p className="text-zinc-500 dark:text-zinc-400">
            Autonomous verification with mandatory human-review checkpoints
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {FEATURES.map((f) => (
            <div
              key={f.title}
              className="p-6 rounded-2xl border border-zinc-100 dark:border-zinc-800 bg-white dark:bg-zinc-900 hover:border-zinc-200 dark:hover:border-zinc-700 transition-colors"
            >
              <div className="w-10 h-10 rounded-xl bg-blue-50 dark:bg-blue-950 flex items-center justify-center mb-4">
                <f.icon className="w-5 h-5 text-blue-600" />
              </div>
              <h3 className="font-semibold text-zinc-900 dark:text-white mb-2">{f.title}</h3>
              <p className="text-sm text-zinc-500 dark:text-zinc-400 leading-relaxed">
                {f.description}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* Compliance */}
      <section className="bg-zinc-50 dark:bg-zinc-900 py-20">
        <div className="max-w-4xl mx-auto px-6 text-center">
          <Lock className="w-8 h-8 text-green-600 mx-auto mb-4" />
          <h2 className="text-3xl font-bold text-zinc-900 dark:text-white mb-3">
            Built for compliance
          </h2>
          <p className="text-zinc-500 dark:text-zinc-400 mb-10">
            GDPR and DPDP Act 2023 requirements built into every workflow
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-6">
            {[
              "Explicit consent",
              "Right to erasure",
              "Full audit trails",
              "Data encryption",
            ].map((item) => (
              <div key={item} className="flex flex-col items-center gap-2">
                <CheckCircle className="w-6 h-6 text-green-600" />
                <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                  {item}
                </span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer CTA */}
      <section className="max-w-4xl mx-auto px-6 py-24 text-center">
        <h2 className="text-3xl font-bold text-zinc-900 dark:text-white mb-4">
          Start verifying smarter
        </h2>
        <p className="text-zinc-500 dark:text-zinc-400 mb-8">
          ~$12/month total cost including voice calls. No per-check fees.
        </p>
        <form
          action={async () => {
            "use server";
            await signIn("google", { redirectTo: "/dashboard" });
          }}
        >
          <button
            type="submit"
            className="px-8 py-3 text-base font-medium bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition-colors"
          >
            Get started for free →
          </button>
        </form>
      </section>

      <footer className="border-t border-zinc-100 dark:border-zinc-800 py-8">
        <div className="max-w-6xl mx-auto px-6 flex items-center justify-between text-sm text-zinc-400">
          <span>© 2025 TrustHire AI</span>
          <div className="flex gap-6">
            <a href="/privacy" className="hover:text-zinc-600 transition-colors">
              Privacy
            </a>
            <a href="/terms" className="hover:text-zinc-600 transition-colors">
              Terms
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}

function GoogleIcon() {
  return (
    <svg viewBox="0 0 24 24" className="w-5 h-5" aria-hidden="true">
      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
      <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
    </svg>
  );
}

const FEATURES = [
  {
    icon: FileText,
    title: "AI resume parsing",
    description:
      "PaddleOCR + Llama 3 extracts structured employment and education data from any resume format — PDF, DOCX, or scanned image.",
  },
  {
    icon: Mail,
    title: "Automated verification emails",
    description:
      "AI-generated, personalised emails sent to HR departments with intelligent reply parsing and automatic follow-ups.",
  },
  {
    icon: Phone,
    title: "AI voice calls",
    description:
      "Autonomous phone calls using Whisper STT and Piper TTS. Full transcripts and AI summaries stored for every call.",
  },
  {
    icon: BarChart3,
    title: "Risk scoring",
    description:
      "Weighted 0–100 risk score with explainable AI reasoning. Every decision is transparent — never a black box.",
  },
  {
    icon: Shield,
    title: "Fraud detection",
    description:
      "Detects overlapping dates, fake institutions, AI-generated resumes, and timeline inconsistencies automatically.",
  },
  {
    icon: Lock,
    title: "Legal compliance",
    description:
      "GDPR and DPDP Act consent workflows, right-to-erasure, full audit logs, and encrypted PII storage.",
  },
];
