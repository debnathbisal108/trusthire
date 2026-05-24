"""
TrustHire AI — API test suite.
Tests all major endpoints with proper fixtures and async support.
"""

import asyncio
import uuid
from datetime import datetime
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

# ─────────────────────────────────────────────────────────────────────────────
# TEST DATABASE SETUP
# ─────────────────────────────────────────────────────────────────────────────

TEST_DATABASE_URL = "postgresql+asyncpg://trusthire:test_password@localhost:5432/trusthire_test"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSession = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(scope="session")
async def setup_db():
    """Create all tables once per test session."""
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from database import Base
    from models import *  # noqa

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db(setup_db) -> AsyncGenerator[AsyncSession, None]:
    """Per-test transactional session that rolls back after each test."""
    async with TestSession() as session:
        async with session.begin():
            yield session
            await session.rollback()


@pytest_asyncio.fixture
async def client(db: AsyncSession):
    """HTTPX async test client with DB override."""
    from main import app
    from database import get_db

    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c

    app.dependency_overrides.clear()


# ─────────────────────────────────────────────────────────────────────────────
# FIXTURES — common test data
# ─────────────────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def org(db: AsyncSession):
    """Create a test organization."""
    from models import Organization
    org = Organization(
        name="Test Corp",
        slug=f"test-corp-{uuid.uuid4().hex[:6]}",
        plan="starter",
    )
    db.add(org)
    await db.flush()
    return org


@pytest_asyncio.fixture
async def admin_user(db: AsyncSession, org):
    """Create an org admin user."""
    from models import User
    user = User(
        email=f"admin-{uuid.uuid4().hex[:6]}@test.com",
        full_name="Test Admin",
        organization_id=org.id,
        role="org_admin",
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def recruiter_user(db: AsyncSession, org):
    """Create a recruiter user."""
    from models import User
    user = User(
        email=f"recruiter-{uuid.uuid4().hex[:6]}@test.com",
        full_name="Test Recruiter",
        organization_id=org.id,
        role="recruiter",
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
def auth_headers(admin_user):
    """JWT headers for the admin user."""
    from security import create_internal_token
    token = create_internal_token(
        str(admin_user.id),
        str(admin_user.organization_id),
        admin_user.role,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
def recruiter_headers(recruiter_user):
    """JWT headers for a recruiter."""
    from security import create_internal_token
    token = create_internal_token(
        str(recruiter_user.id),
        str(recruiter_user.organization_id),
        recruiter_user.role,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def candidate(db: AsyncSession, org, admin_user):
    """Create a test candidate."""
    from models import Candidate
    c = Candidate(
        organization_id=org.id,
        created_by=admin_user.id,
        full_name="Test Candidate",
        status="parsed",
        parsed_data={
            "full_name": "Test Candidate",
            "email": "test@example.com",
            "employment_history": [
                {
                    "company_name": "Acme Corp",
                    "job_title": "Software Engineer",
                    "start_date": "2020-01",
                    "end_date": "2022-06",
                    "company_domain": "acme.com",
                }
            ],
            "education_history": [
                {
                    "institution_name": "MIT",
                    "degree": "BSc",
                    "field_of_study": "Computer Science",
                    "graduation_year": 2019,
                }
            ],
        },
    )
    db.add(c)
    await db.flush()
    return c


@pytest_asyncio.fixture
async def granted_consent(db: AsyncSession, candidate):
    """Pre-grant data_processing consent for a candidate."""
    from models import ConsentRecord
    record = ConsentRecord(
        candidate_id=candidate.id,
        consent_type="data_processing",
        status="granted",
        granted_at=datetime.utcnow(),
        consent_text="Test consent",
        version="1.0",
    )
    db.add(record)
    await db.flush()
    return record


# ─────────────────────────────────────────────────────────────────────────────
# TESTS — /health
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "version" in data


# ─────────────────────────────────────────────────────────────────────────────
# TESTS — /api/v1/candidates
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_candidates_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/candidates/")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_candidates_empty(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/candidates/", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "data" in data
    assert "meta" in data
    assert isinstance(data["data"], list)


@pytest.mark.asyncio
async def test_list_candidates_with_data(
    client: AsyncClient, auth_headers: dict, candidate
):
    resp = await client.get("/api/v1/candidates/", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["meta"]["total"] >= 1
    names = [c["full_name"] for c in data["data"]]
    assert "Test Candidate" in names


@pytest.mark.asyncio
async def test_get_candidate(client: AsyncClient, auth_headers: dict, candidate):
    resp = await client.get(f"/api/v1/candidates/{candidate.id}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(candidate.id)
    assert data["full_name"] == "Test Candidate"


@pytest.mark.asyncio
async def test_get_candidate_not_found(client: AsyncClient, auth_headers: dict):
    resp = await client.get(f"/api/v1/candidates/{uuid.uuid4()}", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_candidate_wrong_org(
    client: AsyncClient,
    db: AsyncSession,
    candidate,
):
    """A user from a different org should not see another org's candidate."""
    from models import Organization, User
    from security import create_internal_token

    other_org = Organization(
        name="Other Corp",
        slug=f"other-corp-{uuid.uuid4().hex[:6]}",
        plan="starter",
    )
    db.add(other_org)
    await db.flush()

    other_user = User(
        email=f"other-{uuid.uuid4().hex[:6]}@test.com",
        full_name="Other User",
        organization_id=other_org.id,
        role="recruiter",
        is_active=True,
    )
    db.add(other_user)
    await db.flush()

    token = create_internal_token(str(other_user.id), str(other_org.id), "recruiter")
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get(f"/api/v1/candidates/{candidate.id}", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_candidates_search(
    client: AsyncClient, auth_headers: dict, candidate
):
    resp = await client.get(
        "/api/v1/candidates/?search=Test", headers=auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert any("Test" in c["full_name"] for c in data["data"])


@pytest.mark.asyncio
async def test_list_candidates_status_filter(
    client: AsyncClient, auth_headers: dict, candidate
):
    resp = await client.get(
        "/api/v1/candidates/?status=parsed", headers=auth_headers
    )
    assert resp.status_code == 200
    for c in resp.json()["data"]:
        assert c["status"] == "parsed"


@pytest.mark.asyncio
async def test_delete_candidate(client: AsyncClient, auth_headers: dict, candidate):
    resp = await client.delete(
        f"/api/v1/candidates/{candidate.id}", headers=auth_headers
    )
    assert resp.status_code == 200
    # Should now 404
    resp2 = await client.get(
        f"/api/v1/candidates/{candidate.id}", headers=auth_headers
    )
    assert resp2.status_code == 404


@pytest.mark.asyncio
async def test_delete_candidate_requires_admin(
    client: AsyncClient, recruiter_headers: dict, candidate
):
    """Recruiters cannot delete candidates."""
    resp = await client.delete(
        f"/api/v1/candidates/{candidate.id}", headers=recruiter_headers
    )
    assert resp.status_code == 403


# ─────────────────────────────────────────────────────────────────────────────
# TESTS — /api/v1/verifications
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_verification_missing_consent(
    client: AsyncClient, auth_headers: dict, candidate
):
    """Verification must fail without data_processing consent."""
    resp = await client.post(
        "/api/v1/verifications/",
        json={"candidate_id": str(candidate.id)},
        headers=auth_headers,
    )
    assert resp.status_code == 403
    data = resp.json()
    assert "CONSENT_MISSING" in str(data)


@pytest.mark.asyncio
async def test_create_verification_with_consent(
    client: AsyncClient,
    auth_headers: dict,
    candidate,
    granted_consent,
    monkeypatch,
):
    """Verification starts successfully when consent is granted."""
    # Patch Celery so it doesn't actually dispatch
    from tasks import celery_app as tasks_module

    class FakeAsyncResult:
        id = "fake-task-id"

    def mock_delay(self, *args, **kwargs):
        return FakeAsyncResult()

    monkeypatch.setattr(
        tasks_module.run_verification_task, "delay", mock_delay
    )

    resp = await client.post(
        "/api/v1/verifications/",
        json={
            "candidate_id": str(candidate.id),
            "config": {
                "check_employment": True,
                "check_education": False,
                "allow_emails": False,
                "allow_voice_calls": False,
            },
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["candidate_id"] == str(candidate.id)
    assert data["status"] in ("pending", "running")


@pytest.mark.asyncio
async def test_get_verification(
    client: AsyncClient,
    auth_headers: dict,
    candidate,
    granted_consent,
    db: AsyncSession,
):
    from models import VerificationRequest
    verif = VerificationRequest(
        organization_id=candidate.organization_id,
        candidate_id=candidate.id,
        status="completed",
        config={},
    )
    db.add(verif)
    await db.flush()

    resp = await client.get(
        f"/api/v1/verifications/{verif.id}", headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_cancel_verification(
    client: AsyncClient,
    auth_headers: dict,
    candidate,
    db: AsyncSession,
    monkeypatch,
):
    from models import VerificationRequest

    verif = VerificationRequest(
        organization_id=candidate.organization_id,
        candidate_id=candidate.id,
        status="running",
        celery_task_id="fake-celery-id",
        config={},
    )
    db.add(verif)
    await db.flush()

    # Patch Celery revoke
    from tasks import celery_app as tasks_module

    monkeypatch.setattr(
        tasks_module.celery_app.control, "revoke", lambda *a, **kw: None
    )

    resp = await client.post(
        f"/api/v1/verifications/{verif.id}/cancel", headers=auth_headers
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_cancel_completed_verification_fails(
    client: AsyncClient,
    auth_headers: dict,
    candidate,
    db: AsyncSession,
):
    from models import VerificationRequest

    verif = VerificationRequest(
        organization_id=candidate.organization_id,
        candidate_id=candidate.id,
        status="completed",
        config={},
    )
    db.add(verif)
    await db.flush()

    resp = await client.post(
        f"/api/v1/verifications/{verif.id}/cancel", headers=auth_headers
    )
    assert resp.status_code == 409


# ─────────────────────────────────────────────────────────────────────────────
# TESTS — Consent
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_consents_empty(
    client: AsyncClient, auth_headers: dict, candidate
):
    resp = await client.get(
        f"/api/v1/candidates/{candidate.id}/consent/", headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_grant_consent(
    client: AsyncClient, auth_headers: dict, candidate
):
    resp = await client.post(
        f"/api/v1/candidates/{candidate.id}/consent/",
        json={"consent_type": "data_processing"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["consent_type"] == "data_processing"
    assert data["status"] == "granted"


@pytest.mark.asyncio
async def test_grant_consent_idempotent(
    client: AsyncClient, auth_headers: dict, candidate, granted_consent
):
    """Granting an already-granted consent returns existing record."""
    resp = await client.post(
        f"/api/v1/candidates/{candidate.id}/consent/",
        json={"consent_type": "data_processing"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    # Should not create duplicate
    list_resp = await client.get(
        f"/api/v1/candidates/{candidate.id}/consent/", headers=auth_headers
    )
    dp_consents = [
        c for c in list_resp.json() if c["consent_type"] == "data_processing"
    ]
    assert len(dp_consents) == 1


@pytest.mark.asyncio
async def test_revoke_consent(
    client: AsyncClient, auth_headers: dict, candidate, granted_consent
):
    resp = await client.delete(
        f"/api/v1/candidates/{candidate.id}/consent/data_processing",
        headers=auth_headers,
    )
    assert resp.status_code == 200

    list_resp = await client.get(
        f"/api/v1/candidates/{candidate.id}/consent/", headers=auth_headers
    )
    dp = [c for c in list_resp.json() if c["consent_type"] == "data_processing"]
    assert all(c["status"] == "revoked" for c in dp)


@pytest.mark.asyncio
async def test_revoke_nonexistent_consent(
    client: AsyncClient, auth_headers: dict, candidate
):
    resp = await client.delete(
        f"/api/v1/candidates/{candidate.id}/consent/voice_call_consent",
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_grant_invalid_consent_type(
    client: AsyncClient, auth_headers: dict, candidate
):
    resp = await client.post(
        f"/api/v1/candidates/{candidate.id}/consent/",
        json={"consent_type": "not_a_real_consent"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# TESTS — Fraud flags
# ─────────────────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def fraud_flag(db: AsyncSession, candidate):
    from models import FraudFlag
    flag = FraudFlag(
        candidate_id=candidate.id,
        flag_type="overlapping_employment",
        severity="high",
        description="Dates overlap by 90 days",
        requires_review=True,
    )
    db.add(flag)
    await db.flush()
    return flag


@pytest.mark.asyncio
async def test_list_fraud_flags(
    client: AsyncClient, auth_headers: dict, candidate, fraud_flag
):
    resp = await client.get(
        f"/api/v1/fraud-flags/candidates/{candidate.id}", headers=auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["flag_type"] == "overlapping_employment"


@pytest.mark.asyncio
async def test_review_fraud_flag_dismiss(
    client: AsyncClient, auth_headers: dict, candidate, fraud_flag
):
    resp = await client.patch(
        f"/api/v1/fraud-flags/{fraud_flag.id}/review",
        json={"outcome": "dismissed"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["review_outcome"] == "dismissed"
    assert data["requires_review"] is False


@pytest.mark.asyncio
async def test_review_fraud_flag_invalid_outcome(
    client: AsyncClient, auth_headers: dict, fraud_flag
):
    resp = await client.patch(
        f"/api/v1/fraud-flags/{fraud_flag.id}/review",
        json={"outcome": "INVALID_OUTCOME"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


# ─────────────────────────────────────────────────────────────────────────────
# TESTS — Admin / usage stats
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_usage(client: AsyncClient, auth_headers: dict, candidate):
    resp = await client.get("/api/v1/admin/usage", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_candidates" in data
    assert "running_verifications" in data
    assert "completed_today" in data
    assert "unreviewed_fraud_flags" in data
    assert data["total_candidates"] >= 1


@pytest.mark.asyncio
async def test_admin_health(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/admin/health", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ─────────────────────────────────────────────────────────────────────────────
# TESTS — Notifications
# ─────────────────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def notification(db: AsyncSession, admin_user, org):
    from models import Notification
    notif = Notification(
        user_id=admin_user.id,
        organization_id=org.id,
        type="verification_complete",
        title="Verification done",
        message="Candidate verified successfully",
        is_read=False,
    )
    db.add(notif)
    await db.flush()
    return notif


@pytest.mark.asyncio
async def test_list_notifications(
    client: AsyncClient, auth_headers: dict, notification
):
    resp = await client.get("/api/v1/notifications/", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    unread = [n for n in data if not n["is_read"]]
    assert len(unread) >= 1


@pytest.mark.asyncio
async def test_mark_notification_read(
    client: AsyncClient, auth_headers: dict, notification
):
    resp = await client.patch(
        f"/api/v1/notifications/{notification.id}/read",
        headers=auth_headers,
    )
    assert resp.status_code == 200

    list_resp = await client.get("/api/v1/notifications/", headers=auth_headers)
    target = next((n for n in list_resp.json() if n["id"] == str(notification.id)), None)
    assert target is not None
    assert target["is_read"] is True


@pytest.mark.asyncio
async def test_mark_all_notifications_read(
    client: AsyncClient, auth_headers: dict, notification
):
    resp = await client.post("/api/v1/notifications/read-all", headers=auth_headers)
    assert resp.status_code == 200

    list_resp = await client.get("/api/v1/notifications/", headers=auth_headers)
    unread = [n for n in list_resp.json() if not n["is_read"]]
    assert len(unread) == 0


# ─────────────────────────────────────────────────────────────────────────────
# TESTS — Fraud detection service (unit tests)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fraud_overlapping_employment():
    from services.fraud.detector import check_overlapping_employment

    employment = [
        {"company_name": "Acme",  "start_date": "2020-01", "end_date": "2021-12"},
        {"company_name": "Globex","start_date": "2021-06", "end_date": "2022-06"},
    ]
    flags = check_overlapping_employment(employment)
    assert len(flags) == 1
    assert flags[0]["flag_type"] == "overlapping_employment"
    assert flags[0]["severity"] == "high"


@pytest.mark.asyncio
async def test_fraud_no_overlap():
    from services.fraud.detector import check_overlapping_employment

    employment = [
        {"company_name": "Acme",  "start_date": "2019-01", "end_date": "2020-12"},
        {"company_name": "Globex","start_date": "2021-01", "end_date": "2022-06"},
    ]
    flags = check_overlapping_employment(employment)
    assert len(flags) == 0


@pytest.mark.asyncio
async def test_fraud_future_graduation():
    from services.fraud.detector import check_education_dates

    education = [{"institution_name": "MIT", "graduation_year": 2099}]
    flags = check_education_dates(education)
    assert len(flags) == 1
    assert flags[0]["flag_type"] == "future_graduation_date"


@pytest.mark.asyncio
async def test_fraud_impossible_graduation():
    from services.fraud.detector import check_education_dates

    education = [{"institution_name": "Old Uni", "graduation_year": 1850}]
    flags = check_education_dates(education)
    assert len(flags) == 1
    assert flags[0]["flag_type"] == "impossible_graduation_date"


@pytest.mark.asyncio
async def test_fraud_suspicious_domain():
    from services.fraud.detector import check_suspicious_hr_domains

    employment = [
        {"company_name": "Acme", "hr_email": "hr@gmail.com"},
        {"company_name": "Globex", "hr_email": "hr@globex.com"},
    ]
    flags = check_suspicious_hr_domains(employment)
    assert len(flags) == 1
    assert "gmail.com" in flags[0]["description"]


@pytest.mark.asyncio
async def test_fraud_duplicate_company():
    from services.fraud.detector import check_duplicate_companies

    employment = [
        {"company_name": "Acme Corp"},
        {"company_name": "Globex"},
        {"company_name": "Acme Corp"},
    ]
    flags = check_duplicate_companies(employment)
    assert len(flags) == 1
    assert flags[0]["flag_type"] == "duplicate_company_entry"


# ─────────────────────────────────────────────────────────────────────────────
# TESTS — Risk scoring (unit tests)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_risk_score_no_data(monkeypatch):
    from services.fraud.scorer import calculate_risk_score

    # Patch AI reasoning so no LLM call needed in unit test
    monkeypatch.setattr(
        "services.fraud.scorer._generate_reasoning",
        lambda *a, **kw: asyncio.coroutine(lambda: "Test reasoning")(),
    )

    result = await calculate_risk_score([], [], [], [])
    assert 0 <= result["overall_score"] <= 100
    assert result["risk_level"] in ("low", "medium", "high", "critical")
    assert "breakdown" in result
    assert "confidence" in result


@pytest.mark.asyncio
async def test_risk_score_all_verified(monkeypatch):
    from services.fraud.scorer import calculate_risk_score

    monkeypatch.setattr(
        "services.fraud.scorer._generate_reasoning",
        lambda *a, **kw: asyncio.coroutine(lambda: "All good")(),
    )

    class FakeEmp:
        verification_status = "verified"

    class FakeEdu:
        verification_status = "verified"

    result = await calculate_risk_score([FakeEmp(), FakeEmp()], [FakeEdu()], [], [])
    assert result["overall_score"] < 30  # Low risk when all verified
    assert result["risk_level"] == "low"


@pytest.mark.asyncio
async def test_risk_score_with_fraud_flags(monkeypatch):
    from services.fraud.scorer import calculate_risk_score

    monkeypatch.setattr(
        "services.fraud.scorer._generate_reasoning",
        lambda *a, **kw: asyncio.coroutine(lambda: "Flags detected")(),
    )

    class FakeFlag:
        severity = "high"
        flag_type = "overlapping_employment"

    result = await calculate_risk_score([], [], [FakeFlag(), FakeFlag()], [])
    assert result["breakdown"]["fraud"]["score"] > 0


# ─────────────────────────────────────────────────────────────────────────────
# TESTS — Security utilities
# ─────────────────────────────────────────────────────────────────────────────

def test_encrypt_decrypt_pii():
    from security import encrypt_pii, decrypt_pii

    original = "test@example.com"
    encrypted = encrypt_pii(original)
    assert encrypted != original
    assert "@" not in encrypted  # Should be opaque
    decrypted = decrypt_pii(encrypted)
    assert decrypted == original


def test_encrypt_empty_string():
    from security import encrypt_pii, decrypt_pii

    assert encrypt_pii("") == ""
    assert decrypt_pii("") == ""


def test_jwt_create_and_decode():
    from security import create_internal_token, decode_jwt

    user_id = str(uuid.uuid4())
    org_id = str(uuid.uuid4())
    token = create_internal_token(user_id, org_id, "recruiter")

    payload = decode_jwt(token)
    assert payload["userId"] == user_id
    assert payload["organizationId"] == org_id
    assert payload["role"] == "recruiter"


def test_jwt_invalid_token():
    from security import decode_jwt

    with pytest.raises(ValueError, match="Invalid token"):
        decode_jwt("not.a.valid.jwt")


def test_jwt_wrong_secret(monkeypatch):
    from security import create_internal_token, decode_jwt
    import security

    token = create_internal_token(str(uuid.uuid4()), str(uuid.uuid4()), "viewer")
    monkeypatch.setattr(security.settings, "nextauth_secret", "completely-different-secret!!!!!")

    with pytest.raises(ValueError):
        decode_jwt(token)


# ─────────────────────────────────────────────────────────────────────────────
# TESTS — Resume parser (unit)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_parse_resume_valid_json(monkeypatch):
    """Parser returns structured data when LLM gives valid JSON."""
    from services.resume_parser import parser

    sample_json = """{
      "full_name": "Jane Smith",
      "email": "jane@example.com",
      "phone": null,
      "linkedin_url": null,
      "employment_history": [
        {
          "company_name": "Acme Corp",
          "job_title": "Engineer",
          "start_date": "2020-01",
          "end_date": "present",
          "location": "New York",
          "responsibilities": ["Built things"],
          "company_domain": "acme.com"
        }
      ],
      "education_history": [],
      "skills": ["Python"],
      "certifications": []
    }"""

    async def mock_invoke(prompt, task="general"):
        return sample_json

    monkeypatch.setattr(parser, "ainvoke_llm", mock_invoke)

    result = await parser.parse_resume("Jane Smith worked at Acme Corp...")
    assert result["full_name"] == "Jane Smith"
    assert len(result["employment_history"]) == 1
    assert result["employment_history"][0]["company_name"] == "Acme Corp"


@pytest.mark.asyncio
async def test_parse_resume_bad_json_returns_empty(monkeypatch):
    """Parser returns empty structure on LLM JSON error."""
    from services.resume_parser import parser

    async def mock_bad(prompt, task="general"):
        return "This is not JSON at all!!"

    monkeypatch.setattr(parser, "ainvoke_llm", mock_bad)

    result = await parser.parse_resume("Some resume text")
    assert result["full_name"] is None
    assert result["employment_history"] == []


@pytest.mark.asyncio
async def test_parse_resume_short_text():
    """Very short text returns empty structure without calling LLM."""
    from services.resume_parser.parser import parse_resume

    result = await parse_resume("Hi")
    assert result["employment_history"] == []


# ─────────────────────────────────────────────────────────────────────────────
# TESTS — Consent service (unit)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_consent_verify_missing_data_processing():
    from services.compliance.consent import verify_consents_for_verification, ConsentMissingError

    candidate_id = str(uuid.uuid4())
    with pytest.raises(ConsentMissingError):
        await verify_consents_for_verification(
            candidate_id,
            {"check_employment": True},
        )


def test_slug_generation():
    from security import generate_slug

    slug = generate_slug("Acme Recruiting Ltd")
    assert "acme" in slug
    assert " " not in slug
    assert len(slug) > 5


# ─────────────────────────────────────────────────────────────────────────────
# TESTS — GDPR erasure
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_gdpr_erase_candidate(
    client: AsyncClient, auth_headers: dict, candidate
):
    resp = await client.delete(
        f"/api/v1/candidates/{candidate.id}/gdpr/erase",
        headers=auth_headers,
    )
    assert resp.status_code == 200

    # Verify candidate is soft-deleted and anonymised
    get_resp = await client.get(
        f"/api/v1/candidates/{candidate.id}", headers=auth_headers
    )
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_gdpr_erase_requires_elevated_role(
    client: AsyncClient, recruiter_headers: dict, candidate
):
    resp = await client.delete(
        f"/api/v1/candidates/{candidate.id}/gdpr/erase",
        headers=recruiter_headers,
    )
    assert resp.status_code == 403


# ─────────────────────────────────────────────────────────────────────────────
# pytest.ini equivalent via pyproject marker
# ─────────────────────────────────────────────────────────────────────────────

# Configure in pyproject.toml or pytest.ini:
#
# [tool.pytest.ini_options]
# asyncio_mode = "auto"
# testpaths = ["tests"]
# filterwarnings = ["ignore::DeprecationWarning"]
