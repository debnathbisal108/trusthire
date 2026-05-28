// lib/auth.ts
import NextAuth from "next-auth";
import Google from "next-auth/providers/google";
import { Pool } from "pg";
import PostgresAdapter from "@auth/pg-adapter";
import { authConfig } from "./auth.config";

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  ssl: process.env.NODE_ENV === "production" ? { rejectUnauthorized: false } : false,
});

export const { handlers, auth, signIn, signOut } = NextAuth({
  ...authConfig,                    // Spread edge config
  adapter: PostgresAdapter(pool),

  providers: [
    Google({
      clientId: process.env.GOOGLE_CLIENT_ID!,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
      authorization: {
        params: {
          prompt: "consent",
          access_type: "offline",
          response_type: "code",
        },
      },
    }),
  ],

  callbacks: {
    ...authConfig.callbacks,        // Keep edge callbacks

    async signIn({ user, account }) {
      if (account?.provider === "google" && user.email) {
        try {
          const client = await pool.connect();
          try {
            const existing = await client.query(
              "SELECT id, organization_id FROM users WHERE email = $1 AND deleted_at IS NULL LIMIT 1",
              [user.email]
            );

            if (existing.rows.length === 0) {
              await client.query("BEGIN");
              const orgName = user.name ? `${user.name.split(" ")[0]}'s Workspace` : "My Workspace";
              const slug = user.email
                .split("@")[0]
                .replace(/[^a-z0-9]/gi, "-")
                .toLowerCase() + "-" + Math.random().toString(36).slice(2, 6);

              const orgResult = await client.query(
                "INSERT INTO organizations (name, slug) VALUES ($1, $2) RETURNING id",
                [orgName, slug]
              );

              const orgId = orgResult.rows[0].id;

              await client.query(
                `INSERT INTO users (google_id, email, full_name, avatar_url, organization_id, role)
                 VALUES ($1, $2, $3, $4, $5, 'org_admin')
                 ON CONFLICT (email) DO UPDATE SET 
                 google_id = $1, organization_id = $5, full_name = $3, avatar_url = $4`,
                [account.providerAccountId, user.email, user.name, user.image, orgId]
              );

              await client.query("COMMIT");
            } else {
              await client.query(
                "UPDATE users SET last_login = NOW(), google_id = $1 WHERE email = $2",
                [account.providerAccountId, user.email]
              );
            }
          } finally {
            client.release();
          }
        } catch (err) {
          console.error("signIn provisioning error:", err);
        }
      }
      return true;
    },

    async jwt({ token, user, account }) {
      if (user?.email) {
        try {
          const result = await pool.query(
            "SELECT id, organization_id, role FROM users WHERE email = $1 AND deleted_at IS NULL LIMIT 1",
            [user.email]
          );

          if (result.rows.length > 0) {
            const dbUser = result.rows[0];
            token.userId = dbUser.id;
            token.organizationId = dbUser.organization_id;
            token.role = dbUser.role;
          }
        } catch (err) {
          console.error("JWT callback DB error:", err);
        }
      }
      return token;
    },
  },
});
