// middleware.ts
import { auth } from "@/lib/auth";
import { NextResponse } from "next/server";

const PUBLIC_ROUTES = ["/", "/login", "/privacy", "/terms"];

export default auth((req) => {
  const { pathname } = req.nextUrl;

  if (
    PUBLIC_ROUTES.includes(pathname) ||
    pathname.startsWith("/api/auth") ||
    pathname.startsWith("/_next") ||
    pathname.startsWith("/favicon") ||
    pathname.startsWith("/public")
  ) {
    return NextResponse.next();
  }

  if (!req.auth?.user) {
    const loginUrl = new URL("/login", req.url);
    loginUrl.searchParams.set("callbackUrl", pathname);
    return NextResponse.redirect(loginUrl);
  }

  const userRole = (req.auth.user as any)?.role ?? "";

  // Role protection
  if (pathname.startsWith("/admin") && !["org_admin", "super_admin"].includes(userRole)) {
    return NextResponse.redirect(new URL("/dashboard?error=unauthorized", req.url));
  }

  if (pathname.startsWith("/compliance") && 
      !["org_admin", "compliance_reviewer", "super_admin"].includes(userRole)) {
    return NextResponse.redirect(new URL("/dashboard?error=unauthorized", req.url));
  }

  return NextResponse.next();
});

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|public/|api/auth).*)"],
};
