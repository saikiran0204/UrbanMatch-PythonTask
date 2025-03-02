from fastapi import FastAPI, HTTPException, Depends, Request
from sqlalchemy.orm import Session
from database import SessionLocal, engine, Base
import models, schemas
from typing import List, Optional
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.responses import JSONResponse
from pydantic import ValidationError
import logging
import json

app = FastAPI()

# Logging setup
logging.basicConfig(filename="app.log", level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize the rate limiter with a global limit
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, lambda request, exc: JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"}))
app.add_middleware(SlowAPIMiddleware)

# Create database tables
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Endpoint to create a new user
@app.post("/users/", response_model=schemas.User)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    # Check if the email is already registered
    existing_user = db.query(models.User).filter(models.User.email == user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered.")
    
    # Create a new user
    db_user = models.User(**user.model_dump())
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    logger.info(f"User created: {db_user.id}")
    return db_user.model_dump()

# Endpoint to read a list of users
@app.get("/users/", response_model=List[schemas.User])
def read_users(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    users = db.query(models.User).filter(models.User.is_active == True).offset(skip).limit(limit).all()
    return [user.model_dump() for user in users]

# Endpoint to read a user by ID
@app.get("/users/{user_id}", response_model=schemas.User)
def read_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user.model_dump()

# Endpoint to update a user by ID
@app.patch("/users/{user_id}")
def update_user(user_id: int, user_update: schemas.UserUpdate, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id, models.User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    update_data = user_update.dict(exclude_unset=True)

    # Check if the new email already exists
    if user_update.email:
        existing_user = db.query(models.User).filter(models.User.email == user_update.email, models.User.id != user_id).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already registered by another user.")

    # Update interests if provided
    if "interests" in update_data:
        update_data["interests"] = json.dumps(update_data["interests"])
    
    # Update user attributes
    for key, value in update_data.items():
        setattr(user, key, value)
    
    db.commit()
    db.refresh(user)
    logger.info(f"User updated: {user_id}")
    return user.model_dump()

# Endpoint to delete (deactivate) a user by ID
@app.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id, models.User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found or already deactivated")
    
    user.is_active = False
    db.commit()
    logger.info(f"User deactivated: {user_id}")
    return {"message": "User deactivated"}

# Endpoint to find matches for a user based on profile information
@app.get("/users/{user_id}/matches")
def find_matches(
    user_id: int, 
    skip: int = 0, 
    limit: int = 5, 
    db: Session = Depends(get_db)
):
    # Retrieve the user by ID
    user = db.query(models.User).filter(models.User.id == user_id, models.User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Retrieve potential matches based on city and gender
    users = db.query(models.User).filter(
        models.User.id != user_id, models.User.is_active == True, models.User.city == user.city, models.User.gender != user.gender
    ).all()
    
    if not users:
        return []

    user_interests = set(json.loads(user.interests))
    matches = []

    for matched_user in users:
        matched_interests = set(json.loads(matched_user.interests))
        
        # Interest Score Calculation (Jaccard Similarity)
        common_interests = user_interests.intersection(matched_interests)
        total_interests = user_interests.union(matched_interests)
        interest_score = len(common_interests) / len(total_interests) if total_interests else 0

        # Age Scoring
        age_difference = abs(user.age - matched_user.age)
        age_score = max(0, 1 - (age_difference / 100))

        # Ensure female's age is less than male's age
        if user.gender == "male" and matched_user.gender == "female":
            if matched_user.age >= user.age:
                age_score = 0
        elif user.gender == "female" and matched_user.gender == "male":
            if user.age >= matched_user.age:
                age_score = 0

        # Final weighted score
        final_score = (0.7 * interest_score) + (0.3 * age_score)

        matches.append({
            "user": matched_user.model_dump(),
            "score": final_score
        })

    # Sort matches by highest score and apply skip & limit
    matches.sort(key=lambda x: x["score"], reverse=True)
    return matches[skip : skip + limit]

