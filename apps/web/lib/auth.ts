// lib/auth.ts
import NextAuth from "next-auth";
import Google from "next-auth/providers/google";
import { Pool } from "pg";
// import PostgresAdapter from "@auth/pg-adapter";
import { authConfig as edgeConfig } from "./auth-edge";

// const pool = new Pool({
//   connectionString: process.env.DATABASE_URL,
//   ssl: process.env.NODE_ENV === "production" ? { rejectUnauthorized: false } : false,
// });

let _pool: Pool | null = null;
function getPool(): Pool {
  if (!_pool) {
    _pool = new Pool({
      connectionString: process.env.DATABASE_URL,
      ssl: process.env.NODE_ENV === "production" ? { rejectUnauthorized: false } : false,
      max: 5,
      idleTimeoutMillis: 30000,
      connectionTimeoutMillis: 5000,
    });
  }
  return _pool;
}

async function getDbUser(email: string) {
  const { rows } = await getPool().query(
    `SELECT id, organization_id, role FROM users WHERE email = $1 AND deleted_at IS NULL LIMIT 1`,
    [email]
  );
  return rows[0] ?? null;
}

async function upsertUser({
  googleId, email, fullName, avatarUrl,
}: { googleId: string; email: string; fullName: string; avatarUrl: string }) {
  const client = await getPool().connect();
  try {
    await client.query("BEGIN");
    const existing = await client.query(
      `SELECT id FROM users WHERE email = $1 AND deleted_at IS NULL LIMIT 1`,
      [email]
    );
    if (existing.rows.length > 0) {
      await client.query(
        `UPDATE users SET last_login=NOW(), google_id=$1,
         full_name=COALESCE(NULLIF($2,''),full_name),
         avatar_url=COALESCE(NULLIF($3,''),avatar_url), updated_at=NOW()
         WHERE email=$4`,
        [googleId, fullName, avatarUrl, email]
      );
    } else {
      const orgName = fullName ? `${fullName.split(" ")[0]}'s Workspace` : "My Workspace";
      const slug = `${email.split("@")[0].replace(/[^a-z0-9]/gi, "-").toLowerCase().slice(0, 30)}-${Math.random().toString(36).slice(2, 7)}`;
      const { rows: [org] } = await client.query(
        `INSERT INTO organizations (name, slug, plan) VALUES ($1, $2, 'starter') RETURNING id`,
        [orgName, slug]
      );
      await client.query(
        `INSERT INTO users (google_id, email, full_name, avatar_url, organization_id, role, last_login)
         VALUES ($1, $2, $3, $4, $5, 'org_admin', NOW())`,
        [googleId, email, fullName, avatarUrl, org.id]
      );
    }
    await client.query("COMMIT");
  } catch (err) {
    await client.query("ROLLBACK");
    throw err;
  } finally {
    client.release();
  }
}

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [
    Google({
      clientId: process.env.GOOGLE_CLIENT_ID!,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
      authorization: {
        params: { prompt: "consent", access_type: "offline", response_type: "code" },
      },
    }),
  ],
  session: { strategy: "jwt", maxAge: 30 * 24 * 60 * 60 },
  callbacks: {
    async signIn({ user, account }) {
      if (account?.provider === "google" && user.email) {
        try {
          await upsertUser({
            googleId: account.providerAccountId,
            email: user.email,
            fullName: user.name ?? "",
            avatarUrl: user.image ?? "",
          });
        } catch (err) {
          console.error("[auth] upsertUser failed:", err);
        }
      }
      return true;
    },
    async jwt({ token, user, account }) {
      if (account?.provider === "google" && user?.email) {
        try {
          const dbUser = await getDbUser(user.email);
          if (dbUser) {
            token.userId = dbUser.id;
            token.organizationId = dbUser.organization_id;
            token.role = dbUser.role;
          }
        } catch (err) {
          console.error("[auth] jwt DB lookup failed:", err);
        }
      }
      return token;
    },
    async session({ session, token }) {
      if (token) {
        (session.user as any).id = token.userId as string;
        (session.user as any).organizationId = token.organizationId as string;
        (session.user as any).role = (token.role as string) ?? "org_admin";
      }
      return session;
    },
  },
  pages: { signIn: "/login", error: "/login" },
  secret: process.env.NEXTAUTH_SECRET,
});
