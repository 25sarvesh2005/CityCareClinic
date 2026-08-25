import os
from common.auth import hash_password
from common.config import should_seed_demo_users
from common.logger import get_logger
from core.constants import UserRole
from core.cruds.user_crud import create_user, find_user_by_email
from core.database.database import get_engine
from core.models.user_model import UserModel

logger = get_logger(__name__)


async def seed_initial_users() -> None:
    """
    Seed default doctor and patient accounts into MongoDB if explicitly enabled.
    Disabled by default and strictly forbidden in production.
    """
    if not should_seed_demo_users():
        logger.debug("Demo user seeding is disabled (SEED_DEMO_USERS=false). Skipping.")
        return

    doctor_password = os.getenv("DEMO_DOCTOR_PASSWORD", "").strip()
    patient_password = os.getenv("DEMO_PATIENT_PASSWORD", "").strip()
    admin_password = os.getenv("DEMO_ADMIN_PASSWORD", "").strip()

    missing_passwords = []
    if not doctor_password:
        missing_passwords.append("DEMO_DOCTOR_PASSWORD")
    if not patient_password:
        missing_passwords.append("DEMO_PATIENT_PASSWORD")
    if not admin_password:
        missing_passwords.append("DEMO_ADMIN_PASSWORD")

    if missing_passwords:
        missing_str = ", ".join(missing_passwords)
        raise ValueError(
            f"SEED_DEMO_USERS is enabled, but required demo password environment variables are missing: {missing_str}"
        )

    try:
        engine = get_engine()
        doctor_email = os.getenv("DOCTOR_EMAIL", "dr.meera@citycare.com").lower().strip()

        # 1. Seed Doctor Account
        existing_doctor = await find_user_by_email(engine, doctor_email)
        if not existing_doctor:
            doctor_user = UserModel(
                name="Dr. Meera Kulkarni",
                email=doctor_email,
                hashed_password=hash_password(doctor_password),
                role=UserRole.DOCTOR,
            )
            await create_user(engine, doctor_user)
            logger.info("Successfully seeded default doctor account: %s", doctor_email)
        else:
            logger.debug("Doctor account already present: %s", doctor_email)

        # 2. Seed Default Patient Account
        patient_email = "rahul.sharma@email.com"
        existing_patient = await find_user_by_email(engine, patient_email)
        if not existing_patient:
            patient_user = UserModel(
                name="Rahul Sharma",
                email=patient_email,
                hashed_password=hash_password(patient_password),
                role=UserRole.PATIENT,
            )
            await create_user(engine, patient_user)
            logger.info("Successfully seeded default patient account: %s", patient_email)
        else:
            logger.debug("Patient account already present: %s", patient_email)

        # 3. Seed Default Super Admin Account
        admin_email = "admin@citycare.com"
        existing_admin = await find_user_by_email(engine, admin_email)
        if not existing_admin:
            admin_user = UserModel(
                name="Platform Super Admin",
                email=admin_email,
                hashed_password=hash_password(admin_password),
                role=UserRole.SUPER_ADMIN,
            )
            await create_user(engine, admin_user)
            logger.info("Successfully seeded default super admin account: %s", admin_email)
        else:
            logger.debug("Super Admin account already present: %s", admin_email)

    except Exception as exc:
        logger.error("Failed to seed initial users: %s", str(exc), exc_info=True)
