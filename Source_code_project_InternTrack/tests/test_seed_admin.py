import io
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

from sqlalchemy.exc import SQLAlchemyError

from app.db import seed_admin


class SeedAdminTests(unittest.TestCase):
    @patch("app.db.seed_admin.seed_default_admin")
    @patch("app.db.seed_admin.SessionLocal")
    def test_database_error_prints_actionable_message(
        self,
        session_local,
        seed_default_admin,
    ) -> None:
        db = session_local.return_value
        seed_default_admin.side_effect = SQLAlchemyError("database details")

        stderr = io.StringIO()
        with (
            patch.object(seed_admin.settings, "APP_ENV", "development"),
            redirect_stderr(stderr),
        ):
            exit_code = seed_admin.main()

        self.assertEqual(exit_code, 1)
        db.close.assert_called_once_with()
        self.assertIn("MySQL", stderr.getvalue())
        self.assertIn("DATABASE_URL", stderr.getvalue())

    @patch("app.db.seed_admin.seed_default_admin")
    @patch("app.db.seed_admin.SessionLocal")
    def test_production_environment_is_rejected(
        self,
        session_local,
        seed_default_admin,
    ) -> None:
        stderr = io.StringIO()
        with (
            patch.object(seed_admin.settings, "APP_ENV", "production"),
            redirect_stderr(stderr),
        ):
            exit_code = seed_admin.main()

        self.assertEqual(exit_code, 1)
        session_local.assert_not_called()
        seed_default_admin.assert_not_called()
        self.assertIn("development", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
