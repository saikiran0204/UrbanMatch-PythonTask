from sqlalchemy import Column, Integer, String, Text, Boolean
import json
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    age = Column(Integer)
    gender = Column(String)
    email = Column(String, unique=True, index=True)
    city = Column(String)
    interests = Column(Text)  # Store interests as a JSON string
    is_active = Column(Boolean, default=True)

    def __init__(self, name, age, gender, email, city, interests):
        self.name = name
        self.age = age
        self.gender = gender
        self.email = email
        self.city = city
        self.interests = json.dumps(interests)  # Serialize list to JSON string
        self.is_active = True

    @property
    def interests_list(self):
        return json.loads(self.interests)  # Deserialize JSON string to list
    

    def model_dump(self):
        self.interests = json.loads(self.interests) 
        return self.__dict__

