from pydantic import BaseModel, EmailStr, Field, model_validator
from typing import Optional


class SignUpSchema(BaseModel):
    full_name: str = Field(..., min_length=1)
    contact_number: Optional[str] = None
    email: EmailStr
    password: str = Field(..., min_length=6)
    confirm_password: str = Field(..., min_length=6)
    captcha_token: Optional[str] = Field(
        default=None,
        description="Google reCAPTCHA token (required when RECAPTCHA_SECRET_KEY is set)",
    )

    @model_validator(mode="after")
    def passwords_match(self) -> "SignUpSchema":
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class SignInSchema(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)


class ResetPasswordSchema(BaseModel):
    email: EmailStr


class UpdatePasswordSchema(BaseModel):
    token: str = Field(..., description="Password reset token or code from email link")
    password: str = Field(..., min_length=6, description="New password")
    confirm_password: str = Field(..., min_length=6, description="Confirm new password")

    @model_validator(mode="after")
    def passwords_match(self) -> "UpdatePasswordSchema":
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class RefreshTokenSchema(BaseModel):
    refresh_token: str


class AcceptTermsSchema(BaseModel):
    # email is now optional - will be extracted from JWT token via verify_auth_token
    name: str = Field(..., min_length=1, description="User's full name for acceptance record")
    date: str = Field(..., description="Acceptance date in YYYY-MM-DD format")


class AcceptPrivacySchema(BaseModel):
    # email is now optional - will be extracted from JWT token via verify_auth_token
    name: str = Field(..., min_length=1, description="User's full name for acceptance record")
    date: str = Field(..., description="Acceptance date in YYYY-MM-DD format")
