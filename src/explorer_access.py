"""Role-based access rules for the PulseIQ self-service KPI Explorer."""

from dataclasses import dataclass
from pathlib import Path
import csv


@dataclass(frozen=True)
class UserAccess:
    username: str
    role: str
    department_id: str | None = None
    team_id: str | None = None


# Demo scopes based on the actual organization records.
DEMO_SCOPES = {
    "ADMIN": UserAccess(
        username="admin.demo",
        role="ADMIN",
    ),
    "HR": UserAccess(
        username="hr.demo",
        role="HR",
        department_id="D07",
    ),
    "MANAGER": UserAccess(
        username="manager.demo",
        role="MANAGER",
        department_id="D03",
        team_id="T08",
    ),
    "EXECUTIVE": UserAccess(
        username="exec.demo",
        role="EXECUTIVE",
    ),
}


ROLE_METRICS = {
    "ADMIN": {f"M{i:02d}" for i in range(1, 29)},
    "HR": {f"M{i:02d}" for i in range(1, 16)} | {"M27"},
    "MANAGER": {"M22", "M23", "M24", "M25"},
    "EXECUTIVE": {
        "M01", "M02", "M03", "M04", "M05", "M06",
        "M16", "M17", "M18", "M19", "M20",
    },
}


def load_demo_users(csv_path=None):
    """Load demo usernames and roles from the supplied starter CSV."""
    if csv_path is None:
        csv_path = (
            Path(__file__).resolve().parents[1]
            / "05_Starter"
            / "demo_users.csv"
        )

    users = {}

    with Path(csv_path).open(
        newline="",
        encoding="utf-8-sig",
    ) as file:
        for row in csv.DictReader(file):
            username = row["username"].strip()
            role = row["role"].strip().upper()

            if role not in DEMO_SCOPES:
                raise ValueError(f"Unsupported demo role: {role}")

            if DEMO_SCOPES[role].username != username:
                raise ValueError(
                    f"Demo user mapping mismatch for {username}"
                )

            users[username] = DEMO_SCOPES[role]

    return users


def get_user_access(username, csv_path=None):
    """Return the configured access scope for a demo username."""
    users = load_demo_users(csv_path)

    if username not in users:
        raise PermissionError("Unknown demo user")

    return users[username]


def can_access_metric(user, metric_id):
    """Check whether a role is allowed to request a metric."""
    if user.role not in ROLE_METRICS:
        return False

    return metric_id in ROLE_METRICS[user.role]


def get_allowed_dimensions(user):
    """Return dimensions available to the user's role."""
    if user.role == "ADMIN":
        return ["company", "department", "team"]

    if user.role == "HR":
        return ["department"]

    if user.role == "MANAGER":
        return ["team"]

    if user.role == "EXECUTIVE":
        return ["company"]

    return []


def get_scope_filter(user):
    """Return the mandatory organizational scope for query filtering."""
    if user.role == "ADMIN":
        return {}

    if user.role == "HR":
        return {"department_id": user.department_id}

    if user.role == "MANAGER":
        return {
            "department_id": user.department_id,
            "team_id": user.team_id,
        }

    if user.role == "EXECUTIVE":
        return {"company_level_only": True}

    raise PermissionError("Unsupported role")
