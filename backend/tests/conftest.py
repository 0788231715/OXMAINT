import os

from sqlalchemy.engine import make_url

from backend.app.config import settings


TEST_DATABASE_NAME = "oxmaint_test_db"

application_url = make_url(settings.DATABASE_URL)

if application_url.database == TEST_DATABASE_NAME:
    raise RuntimeError(
        "The application DATABASE_URL must not already point "
        "to the test database."
    )

test_url = application_url.set(database=TEST_DATABASE_NAME)

if test_url.database != TEST_DATABASE_NAME:
    raise RuntimeError("Test database safety check failed.")

settings.DATABASE_URL = test_url.render_as_string(
    hide_password=False
)

os.environ["DATABASE_URL"] = settings.DATABASE_URL
