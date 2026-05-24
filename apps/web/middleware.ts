import { auth } from "@/lib/auth";
import { NextResponse } from "next/server";

const PUBLIC_ROUTES = ["/", "/login", "/privacy", "/terms"];

const ROLE_PROTECTED: Record<string, string[]> = {
  "/compliance": ["org_admin", "compliance_reviewer", "super_admin"],
  "/admin":      ["org_admin", "super_admin"],
};

export default auth((req) => {
  const { pathname } = req.nextUrl;

  // Always allow public routes and NextAuth internals
  if (
    PUBLIC_ROUTES.includes(pathname) ||
    pathname.startsWith("/api/auth") ||
    pathname.startsWith("/_next") ||
    pathname.startsWith("/favicon")
  ) {
    return NextResponse.next();
  }

  // Unauthenticated → redirect to login
  if (!req.auth) {
    const loginUrl = new URL("/login", req.url);
    loginUrl.searchParams.set("callbackUrl", pathname);
    return NextResponse.redirect(loginUrl);
  }

  const userRole = (req.auth.user as any)?.role ?? "";

  // Role-gated routes
  for (const [prefix, allowedRoles] of Object.entries(ROLE_PROTECTED)) {
    if (pathname.startsWith(prefix) && !allowedRoles.includes(userRole)) {
      return NextResponse.redirect(new URL("/dashboard", req.url));
    }
  }

  return NextResponse.next();
});

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|api/auth).*)"],
};
