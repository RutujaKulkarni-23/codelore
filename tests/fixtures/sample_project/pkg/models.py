from dataclasses import dataclass


@dataclass
class UserRecord:
    user_id: str
    username: str
    email: str

    def get_display_name(self) -> str:
        """Returns sanitized username."""
        return self.username.strip().title()

    def update_email(self, new_email: str) -> bool:
        """Updates user email after format validation."""
        if "@" in new_email and "." in new_email:
            self.email = new_email.strip()
            return True
        return False
