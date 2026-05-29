/**
 * ensure-db-tables.js
 * Runs before `next build` on Render.
 * Creates organizations + users tables if they don't already exist.
 * Full schema managed by Alembic (API side) — this is a safety net.
 */
const { Pool } = require("pg");

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  ssl: process.env.NODE_ENV === "production" ? { rejectUnauthorized: false } : false,
});

async function run() {
  console.log("[db-setup] checking tables...");
  const client = await pool.connect();
  try {
    const { rows } = await client.query(`
      SELECT table_name FROM information_schema.tables
      WHERE table_schema='public' AND table_name IN ('organizations','users')
    `);
    const have = new Set(rows.map(r => r.table_name));

    await client.query(`CREATE EXTENSION IF NOT EXISTS "uuid-ossp"`);

    if (!have.has("organizations")) {
      await client.query(`
        CREATE TABLE organizations (
          id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
          name       VARCHAR(255) NOT NULL,
          slug       VARCHAR(100) UNIQUE NOT NULL,
          plan       VARCHAR(50)  DEFAULT 'starter',
          settings   JSONB        DEFAULT '{}',
          created_at TIMESTAMPTZ  DEFAULT NOW(),
          updated_at TIMESTAMPTZ  DEFAULT NOW(),
          deleted_at TIMESTAMPTZ
        )
      `);
      console.log("[db-setup] ✅ created organizations");
    } else {
      console.log("[db-setup] ✅ organizations exists");
    }

    if (!have.has("users")) {
      await client.query(`
        CREATE TABLE users (
          id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
          organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
          google_id       VARCHAR(255) UNIQUE,
          email           VARCHAR(255) NOT NULL UNIQUE,
          full_name       VARCHAR(255),
          avatar_url      TEXT,
          role            VARCHAR(50) NOT NULL DEFAULT 'org_admin',
          is_active       BOOLEAN DEFAULT TRUE,
          last_login      TIMESTAMPTZ,
          created_at      TIMESTAMPTZ DEFAULT NOW(),
          updated_at      TIMESTAMPTZ DEFAULT NOW(),
          deleted_at      TIMESTAMPTZ
        );
        CREATE INDEX idx_users_email ON users(email) WHERE deleted_at IS NULL;
      `);
      console.log("[db-setup] ✅ created users");
    } else {
      console.log("[db-setup] ✅ users exists");
    }

    console.log("[db-setup] done.");
  } catch (err) {
    console.error("[db-setup] error (non-fatal):", err.message);
  } finally {
    client.release();
    await pool.end();
  }
}

run();
