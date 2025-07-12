from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import json
import asyncio
import aiohttp
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Dict, Set
import uuid
from datetime import datetime


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_sessions: Dict[str, str] = {}  # websocket_id -> username

    async def connect(self, websocket: WebSocket, user_id: str, username: str):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        self.user_sessions[user_id] = username
        # Broadcast user joined
        await self.broadcast_user_list()

    def disconnect(self, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
        if user_id in self.user_sessions:
            del self.user_sessions[user_id]

    async def send_personal_message(self, message: str, user_id: str):
        if user_id in self.active_connections:
            await self.active_connections[user_id].send_text(message)

    async def broadcast(self, message: str):
        for user_id, connection in self.active_connections.items():
            try:
                await connection.send_text(message)
            except:
                # Remove stale connection
                self.disconnect(user_id)

    async def broadcast_user_list(self):
        online_users = [
            {"id": user_id, "username": username} 
            for user_id, username in self.user_sessions.items()
        ]
        message = json.dumps({
            "type": "users_online",
            "users": online_users
        })
        await self.broadcast(message)

    def get_online_users(self):
        return [
            {"id": user_id, "username": username} 
            for user_id, username in self.user_sessions.items()
        ]

manager = ConnectionManager()

# Flask relay server URLs
FLASK_RELAY_URLS = [
    "http://10.0.2.15:5000",
    "http://127.0.0.1:5000"
]

# Data Models
class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    username: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_seen: datetime = Field(default_factory=datetime.utcnow)

class Message(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    username: str
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    relay_sent: bool = False

class UserCreate(BaseModel):
    username: str

class MessageCreate(BaseModel):
    content: str

# Helper function to send to Flask relay server
async def send_to_relay_server(message_data: dict):
    """Try to send message to Flask relay server"""
    for url in FLASK_RELAY_URLS:
        try:
            async with aiohttp.ClientSession() as session:
                # Try common endpoints
                endpoints = ["/message", "/send_message", "/api/message", "/"]
                for endpoint in endpoints:
                    try:
                        async with session.post(
                            f"{url}{endpoint}",
                            json=message_data,
                            timeout=aiohttp.ClientTimeout(total=2)
                        ) as response:
                            if response.status == 200:
                                logger.info(f"Message sent to relay server {url}{endpoint}")
                                return True
                    except:
                        continue
        except Exception as e:
            logger.warning(f"Failed to send to relay server {url}: {e}")
            continue
    return False

# API Routes
@api_router.post("/register", response_model=User)
async def register_user(user_data: UserCreate):
    # Check if username already exists
    existing_user = await db.users.find_one({"username": user_data.username})
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    user = User(username=user_data.username)
    await db.users.insert_one(user.dict())
    return user

@api_router.get("/users/online")
async def get_online_users():
    return {"users": manager.get_online_users()}

@api_router.get("/messages", response_model=List[Message])
async def get_messages(limit: int = 50):
    messages = await db.messages.find().sort("timestamp", -1).limit(limit).to_list(limit)
    return [Message(**msg) for msg in reversed(messages)]

@api_router.post("/test-relay")
async def test_relay_connection():
    """Test connection to Flask relay server"""
    test_message = {
        "type": "test",
        "message": "Connection test from chat app",
        "timestamp": datetime.utcnow().isoformat()
    }
    
    success = await send_to_relay_server(test_message)
    return {"relay_connection": "success" if success else "failed"}

# WebSocket endpoint
@api_router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str, username: str = "Anonymous"):
    await manager.connect(websocket, user_id, username)
    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            if message_data["type"] == "message":
                # Create message object
                message = Message(
                    user_id=user_id,
                    username=username,
                    content=message_data["content"]
                )
                
                # Save to database
                await db.messages.insert_one(message.dict())
                
                # Prepare message for broadcast
                broadcast_message = {
                    "type": "message",
                    "id": message.id,
                    "user_id": message.user_id,
                    "username": message.username,
                    "content": message.content,
                    "timestamp": message.timestamp.isoformat()
                }
                
                # Broadcast to all connected clients
                await manager.broadcast(json.dumps(broadcast_message))
                
                # Try to send to Flask relay server
                relay_data = {
                    "user": username,
                    "message": message.content,
                    "timestamp": message.timestamp.isoformat(),
                    "user_id": user_id
                }
                
                relay_sent = await send_to_relay_server(relay_data)
                if relay_sent:
                    # Update message as relay sent
                    await db.messages.update_one(
                        {"id": message.id},
                        {"$set": {"relay_sent": True}}
                    )
                
    except WebSocketDisconnect:
        manager.disconnect(user_id)
        await manager.broadcast_user_list()

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()