"use client";

import { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import {
  Upload, FileText, ArrowLeft, AlertCircle, CheckCircle, Loader2,
} from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/utils";

const ACCEPT_TYPES = ".pdf,.docx,.png,.jpg,.jpeg,.webp";
const MAX_MB = 10;

export default function NewCandidatePage() {
  const router = useRouter();
  const fileRef = useRef<HTMLInputElement>(null);

  const [fullName, setFullName]   = useState("");
  const [email, setEmail]         = useState("");
  const [phone, setPhone]         = useState("");
  const [linkedin, setLinkedin]   = useState("");
  const [file, setFile]           = useState<File | null>(null);
  const [dragOver, setDragOver]   = useState(false);
  const [error, setError]         = useState("");

  const createCandidate = useMutation({
    mutationFn: (fd: FormData) => apiClient.candidates.create(fd),
    onSuccess: (candidate) => {
      router.push(`/candidates/${candidate.id}`);
    },
    onError: (err: any) => {
      setError(err.message ?? "Failed to create candidate. Please try again.");
    },
  });

  const handleFile = (f: File) => {
    if (f.size > MAX_MB * 1024 * 1024) {
      setError(`File is too large. Maximum size is ${MAX_MB} MB.`);
      return;
    }
    setError("");
    setFile(f);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (!fullName.trim()) {
      setError("Candidate name is required.");
      return;
    }
    if (!file) {
      setError("Please upload a resume.");
      return;
    }

    const fd = new FormData();
    fd.append("full_name", fullName.trim());
    fd.append("resume", file);
    if (email.trim())   fd.append("email",        email.trim());
    if (phone.trim())   fd.append("phone",        phone.trim());
    if (linkedin.trim()) fd.append("linkedin_url", linkedin.trim());

    createCandidate.mutate(fd);
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Back */}
      <Link
        href="/candidates"
        className="inline-flex items-center gap-1.5 text-sm text-zinc-500 hover:text-zinc-900 dark:hover:text-white transition-colors"
      >
        <ArrowLeft className="w-3.5 h-3.5" /> Back to candidates
      </Link>

      <div>
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-white">Add candidate</h1>
        <p className="text-zinc-500 dark:text-zinc-400 text-sm mt-1">
          Upload a resume and TrustHire AI will automatically extract employment and education data.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Name */}
        <div>
          <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1.5">
            Full name <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            placeholder="Jane Smith"
            required
            className="w-full px-3 py-2.5 text-sm border border-zinc-200 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-900 text-zinc-900 dark:text-white placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {/* Email + Phone row */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1.5">
              Email (optional)
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="jane@example.com"
              className="w-full px-3 py-2.5 text-sm border border-zinc-200 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-900 text-zinc-900 dark:text-white placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1.5">
              Phone (optional)
            </label>
            <input
              type="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="+1 555 000 0000"
              className="w-full px-3 py-2.5 text-sm border border-zinc-200 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-900 text-zinc-900 dark:text-white placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>

        {/* LinkedIn */}
        <div>
          <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1.5">
            LinkedIn URL (optional)
          </label>
          <input
            type="url"
            value={linkedin}
            onChange={(e) => setLinkedin(e.target.value)}
            placeholder="https://linkedin.com/in/jane-smith"
            className="w-full px-3 py-2.5 text-sm border border-zinc-200 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-900 text-zinc-900 dark:text-white placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {/* Resume upload */}
        <div>
          <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1.5">
            Resume / CV <span className="text-red-500">*</span>
          </label>

          {/* Drop zone */}
          <div
            onDrop={handleDrop}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onClick={() => fileRef.current?.click()}
            className={cn(
              "relative border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors",
              dragOver
                ? "border-blue-500 bg-blue-50 dark:bg-blue-950"
                : file
                ? "border-green-400 bg-green-50 dark:bg-green-950"
                : "border-zinc-200 dark:border-zinc-700 hover:border-zinc-300 dark:hover:border-zinc-600"
            )}
          >
            <input
              ref={fileRef}
              type="file"
              accept={ACCEPT_TYPES}
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) handleFile(f);
              }}
            />

            {file ? (
              <div className="flex flex-col items-center gap-2">
                <CheckCircle className="w-10 h-10 text-green-500" />
                <p className="font-medium text-zinc-900 dark:text-white">{file.name}</p>
                <p className="text-sm text-zinc-500">
                  {(file.size / (1024 * 1024)).toFixed(1)} MB
                </p>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    setFile(null);
                    if (fileRef.current) fileRef.current.value = "";
                  }}
                  className="text-xs text-red-500 hover:underline mt-1"
                >
                  Remove
                </button>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-3">
                <div className="w-12 h-12 rounded-xl bg-zinc-100 dark:bg-zinc-800 flex items-center justify-center">
                  <Upload className="w-6 h-6 text-zinc-400" />
                </div>
                <div>
                  <p className="font-medium text-zinc-700 dark:text-zinc-300">
                    Drop resume here or click to browse
                  </p>
                  <p className="text-sm text-zinc-400 mt-1">
                    PDF, DOCX, PNG, JPEG — max {MAX_MB} MB
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Privacy notice */}
        <div className="bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded-lg px-4 py-3 text-xs text-blue-700 dark:text-blue-300">
          <strong>Privacy notice:</strong> Candidate personal data is encrypted at rest.
          Verification will only begin after explicit candidate consent is recorded.
          Data is processed under GDPR Article 6(1)(a).
        </div>

        {/* Error */}
        {error && (
          <div className="flex items-start gap-2 text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg px-4 py-3">
            <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
            {error}
          </div>
        )}

        {/* Submit */}
        <button
          type="submit"
          disabled={createCandidate.isPending}
          className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-blue-600 text-white font-medium rounded-xl hover:bg-blue-700 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
        >
          {createCandidate.isPending ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Uploading & parsing…
            </>
          ) : (
            <>
              <FileText className="w-4 h-4" />
              Upload resume
            </>
          )}
        </button>
      </form>
    </div>
  );
}
