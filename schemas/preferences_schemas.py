from pydantic import BaseModel, Field

class FeedbackIntensitySchema(BaseModel):
    intensity: int = Field(..., ge=0, le=10, description="Feedback intensity scale from 0 (gentle) to 10 (very challenging)")

class UserPreferencesSchema(BaseModel):
    feedback_intensity: int = Field(default=5, ge=0, le=10, description="Angel constructive feedback intensity (0-10)")
    communication_style: str = Field(default="professional", description="Preferred communication style")
    
    class Config:
        json_schema_extra = {
            "example": {
                "feedback_intensity": 5,
                "communication_style": "professional"
            }
        }

