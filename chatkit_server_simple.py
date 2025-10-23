#!/usr/bin/env python3
"""
Simple ChatKit Server for Pet Food Assistant

This follows the official ChatKit documentation pattern exactly.
"""

import logging
import os
import sys
import uuid
from typing import Any, AsyncIterator

# Add current directory to path for imports
sys.path.append(os.path.dirname(__file__))

# ChatKit imports
from chatkit.server import ChatKitServer, StreamingResult
from chatkit.types import ThreadMetadata, UserMessageItem, ThreadStreamEvent, UserMessageContent, Attachment, AttachmentCreateParams, ImageAttachment, FileAttachment
from chatkit.store import Store, AttachmentStore
from chatkit.agents import AgentContext, stream_agent_response, simple_to_agent_input, ThreadItemConverter

# Agents imports
from agents.agent import Agent
from agents.run import Runner, RunConfig

# Pet agent import
from pet_agent import pet_asistant

# FastAPI imports
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, Response
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =============================================================================
# SIMPLE CHATKIT SERVER IMPLEMENTATION
# =============================================================================

class PetChatKitServer(ChatKitServer):
    """
    Simple ChatKit server following official documentation pattern.
    """
    
    def __init__(self, data_store: Store, attachment_store=None):
        super().__init__(data_store, attachment_store)
        self.converter = PetAssistantThreadItemConverter(data_store)
        logger.info("Pet ChatKit server initialized")
    
    async def respond(
        self,
        thread: ThreadMetadata,
        input: UserMessageItem | None,
        context: Any,
    ) -> AsyncIterator[ThreadStreamEvent]:
        """
        Handle ChatKit requests following official documentation pattern.
        """
        logger.info(f"Processing request for thread {thread.id}")
        
        # Create agent context
        agent_context = AgentContext(
            thread=thread,
            store=self.store,
            request_context=context,
        )
        
        # Get previous_response_id from thread metadata for conversation continuity
        previous_response_id = thread.metadata.get("previous_response_id")
        logger.info(f"Previous response ID: {previous_response_id}")
        
        # Convert input to agent format - use previous_response_id optimization
        if input:
            if previous_response_id:
                # If we have a previous_response_id, only send the current message
                # The Agent SDK will use previous_response_id to reference the conversation history
                agent_input = await self.converter.to_agent_input([input])
                logger.info("Using previous_response_id optimization - sending only current message")
            else:
                # First message - load all conversation history
                thread_items = await self.store.load_thread_items(
                    thread.id, None, 100, "asc", context
                )
                logger.info(f"First message - loaded {len(thread_items.data)} items from thread {thread.id}")
                agent_input = await self.converter.to_agent_input(thread_items.data)
        else:
            agent_input = []
        
        logger.info(f"Agent input: {agent_input}")
        
        # Run agent using official pattern with custom workflow name and previous_response_id
        result = Runner.run_streamed(
            pet_asistant,
            agent_input,
            context=agent_context,
            previous_response_id=previous_response_id,
            run_config=RunConfig(workflow_name="Pet Food Assistant Workflow")
        )
        
        # Stream response
        logger.info("Starting to stream agent response...")
        event_count = 0
        async for event in stream_agent_response(agent_context, result):
            event_count += 1
            # Only log important events, not every update
            if event_count == 1 or "Done" in type(event).__name__ or "Error" in type(event).__name__:
                logger.info(f"Streaming event {event_count}: {type(event).__name__}")
            yield event
        
        logger.info(f"Finished streaming {event_count} events")
        
        # Save the response_id for conversation continuity
        if result.last_response_id:
            thread.metadata["previous_response_id"] = result.last_response_id
            await self.store.save_thread(thread, context)
            logger.info(f"Saved previous_response_id: {result.last_response_id}")

# =============================================================================
# SIMPLE SQLITE STORE
# =============================================================================

import sqlite3
import json
import uuid
from datetime import datetime

class SimpleSQLiteStore(Store[Any]):
    """Simple SQLite store for development."""
    
    def __init__(self, db_path: str = "pet_chat.db"):
        self.db_path = db_path
        self._create_tables()
    
    def _create_connection(self):
        return sqlite3.connect(self.db_path)
    
    def _create_tables(self):
        with self._create_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS threads (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    data TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS items (
                    id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    data TEXT NOT NULL
                )
            """)
            conn.commit()
    
    def generate_thread_id(self, context: Any) -> str:
        return f"cthr_{uuid.uuid4().hex[:8]}"
    
    def generate_item_id(self, item_type: str, thread: ThreadMetadata, context: Any) -> str:
        return f"cti_{uuid.uuid4().hex[:8]}"
    
    async def load_thread(self, thread_id: str, context: Any) -> ThreadMetadata:
        with self._create_connection() as conn:
            cursor = conn.execute("SELECT data FROM threads WHERE id = ?", (thread_id,)).fetchone()
            if cursor is None:
                raise Exception(f"Thread {thread_id} not found")
            data = json.loads(cursor[0])
            return ThreadMetadata(**data)
    
    async def save_thread(self, thread: ThreadMetadata, context: Any) -> None:
        with self._create_connection() as conn:
            # Use model_dump with mode='json' to handle datetime serialization
            data = json.dumps(thread.model_dump(mode='json'))
            conn.execute(
                "INSERT OR REPLACE INTO threads (id, created_at, data) VALUES (?, ?, ?)",
                (thread.id, thread.created_at.isoformat(), data)
            )
            conn.commit()
    
    async def load_thread_items(self, thread_id: str, after: str | None, limit: int, order: str, context: Any):
        with self._create_connection() as conn:
            query = "SELECT data FROM items WHERE thread_id = ?"
            params = [thread_id]
            if after:
                query += " AND id > ?"
                params.append(after)
            query += f" ORDER BY id {order} LIMIT ?"
            params.append(limit)
            
            cursor = conn.execute(query, params)
            items = []
            for row in cursor:
                data = json.loads(row[0])
                # Create the appropriate ThreadItem subclass based on type
                item_type = data.get("type")
                if item_type == "user_message":
                    from chatkit.types import UserMessageItem
                    items.append(UserMessageItem(**data))
                elif item_type == "assistant_message":
                    from chatkit.types import AssistantMessageItem
                    items.append(AssistantMessageItem(**data))
                elif item_type == "client_tool_call":
                    from chatkit.types import ClientToolCallItem
                    items.append(ClientToolCallItem(**data))
                elif item_type == "widget":
                    from chatkit.types import WidgetItem
                    items.append(WidgetItem(**data))
                elif item_type == "workflow":
                    from chatkit.types import WorkflowItem
                    items.append(WorkflowItem(**data))
                elif item_type == "task":
                    from chatkit.types import TaskItem
                    items.append(TaskItem(**data))
                elif item_type == "hidden_context":
                    from chatkit.types import HiddenContextItem
                    items.append(HiddenContextItem(**data))
                elif item_type == "end_of_turn":
                    from chatkit.types import EndOfTurnItem
                    items.append(EndOfTurnItem(**data))
                else:
                    # Fallback to UserMessageItem for unknown types
                    from chatkit.types import UserMessageItem
                    items.append(UserMessageItem(**data))
            
            from chatkit.types import Page
            return Page(data=items, has_more=False, after=None)
    
    async def save_attachment(self, attachment: Any, context: Any) -> None:
        """Save attachment data to database."""
        with self._create_connection() as conn:
            # Extract base64 data from attachment
            if hasattr(attachment, 'data'):
                data = attachment.data
            elif isinstance(attachment, dict) and 'data' in attachment:
                data = attachment['data']
            else:
                # For ImageAttachment/FileAttachment objects, we need to get the actual data
                # This will be handled by the attachment store
                data = ""
            
            conn.execute(
                "INSERT OR REPLACE INTO attachments (id, name, mime_type, size, data, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    attachment.id if hasattr(attachment, 'id') else attachment.get('id'),
                    attachment.name if hasattr(attachment, 'name') else attachment.get('name'),
                    attachment.mime_type if hasattr(attachment, 'mime_type') else attachment.get('mime_type'),
                    attachment.size if hasattr(attachment, 'size') else attachment.get('size', 0),
                    data,
                    datetime.now().isoformat()
                )
            )
            conn.commit()
    
    async def load_attachment(self, attachment_id: str, context: Any):
        """Load attachment from database."""
        logger.info(f"Loading attachment with ID: {attachment_id}")
        
        with self._create_connection() as conn:
            # Debug: Show all attachments in database
            all_attachments = conn.execute("SELECT id, name FROM attachments").fetchall()
            logger.info(f"All attachments in database: {all_attachments}")
            
            cursor = conn.execute("SELECT * FROM attachments WHERE id = ?", (attachment_id,)).fetchone()
            if cursor is None:
                logger.error(f"Attachment {attachment_id} not found in database")
                raise Exception(f"Attachment {attachment_id} not found")
            
            logger.info(f"Found attachment: {cursor[0]} - {cursor[1]}")
            
            # Extract data from database
            id_val = cursor[0]
            name = cursor[1]
            mime_type = cursor[2]
            size = cursor[3]
            data = cursor[4]
            created_at = cursor[5]
            
            # Return proper ChatKit attachment object with type discriminator
            from chatkit.types import ImageAttachment, FileAttachment
            
            if mime_type and mime_type.startswith("image/"):
                return ImageAttachment(
                    id=id_val,
                    name=name,
                    mime_type=mime_type,
                    upload_url=None,
                    preview_url=f"data:{mime_type};base64,{data}" if data else None
                )
            else:
                return FileAttachment(
                    id=id_val,
                    name=name,
                    mime_type=mime_type,
                    upload_url=None
                )
    
    async def delete_attachment(self, attachment_id: str, context: Any) -> None:
        """Delete attachment from database."""
        with self._create_connection() as conn:
            conn.execute("DELETE FROM attachments WHERE id = ?", (attachment_id,))
            conn.commit()
    
    async def load_threads(self, limit: int, after: str | None, order: str, context: Any):
        with self._create_connection() as conn:
            query = "SELECT data FROM threads"
            params = []
            if after:
                query += " WHERE id > ?"
                params.append(after)
            query += f" ORDER BY id {order} LIMIT ?"
            params.append(limit)
            
            cursor = conn.execute(query, params)
            threads = []
            for row in cursor:
                data = json.loads(row[0])
                threads.append(ThreadMetadata(**data))
            
            from chatkit.types import Page
            return Page(data=threads, has_more=False, after=None)
    
    async def add_thread_item(self, thread_id: str, item: Any, context: Any) -> None:
        with self._create_connection() as conn:
            data = json.dumps(item.model_dump(mode='json'))
            try:
                conn.execute(
                    "INSERT INTO items (id, thread_id, created_at, data) VALUES (?, ?, ?, ?)",
                    (item.id, thread_id, item.created_at.isoformat(), data)
                )
                conn.commit()
            except sqlite3.IntegrityError as e:
                if "UNIQUE constraint failed" in str(e):
                    logger.warning(f"Item {item.id} already exists, skipping duplicate insert")
                    # This is expected behavior - ChatKit shouldn't add duplicates
                    # but if it does, we gracefully handle it
                else:
                    raise
    
    async def save_item(self, thread_id: str, item: Any, context: Any) -> None:
        with self._create_connection() as conn:
            data = json.dumps(item.model_dump(mode='json'))
            conn.execute(
                "UPDATE items SET data = ? WHERE id = ? AND thread_id = ?",
                (data, item.id, thread_id)
            )
            conn.commit()
    
    async def load_item(self, thread_id: str, item_id: str, context: Any):
        with self._create_connection() as conn:
            cursor = conn.execute(
                "SELECT data FROM items WHERE id = ? AND thread_id = ?",
                (item_id, thread_id)
            ).fetchone()
            if cursor is None:
                raise Exception(f"Item {item_id} not found")
            data = json.loads(cursor[0])
            
            # Create the appropriate ThreadItem subclass based on type
            item_type = data.get("type")
            if item_type == "user_message":
                from chatkit.types import UserMessageItem
                return UserMessageItem(**data)
            elif item_type == "assistant_message":
                from chatkit.types import AssistantMessageItem
                return AssistantMessageItem(**data)
            elif item_type == "client_tool_call":
                from chatkit.types import ClientToolCallItem
                return ClientToolCallItem(**data)
            elif item_type == "widget":
                from chatkit.types import WidgetItem
                return WidgetItem(**data)
            elif item_type == "workflow":
                from chatkit.types import WorkflowItem
                return WorkflowItem(**data)
            elif item_type == "task":
                from chatkit.types import TaskItem
                return TaskItem(**data)
            elif item_type == "hidden_context":
                from chatkit.types import HiddenContextItem
                return HiddenContextItem(**data)
            elif item_type == "end_of_turn":
                from chatkit.types import EndOfTurnItem
                return EndOfTurnItem(**data)
            else:
                # Fallback to UserMessageItem for unknown types
                from chatkit.types import UserMessageItem
                return UserMessageItem(**data)
    
    async def delete_thread(self, thread_id: str, context: Any) -> None:
        with self._create_connection() as conn:
            conn.execute("DELETE FROM threads WHERE id = ?", (thread_id,))
            conn.execute("DELETE FROM items WHERE thread_id = ?", (thread_id,))
            conn.commit()
    
    async def delete_thread_item(self, thread_id: str, item_id: str, context: Any) -> None:
        with self._create_connection() as conn:
            conn.execute(
                "DELETE FROM items WHERE id = ? AND thread_id = ?",
                (item_id, thread_id)
            )
            conn.commit()

# =============================================================================
# SIMPLE SQLITE ATTACHMENT STORE
# =============================================================================

class SimpleSQLiteAttachmentStore(AttachmentStore[Any]):
    """Simple SQLite attachment store for development."""
    
    def __init__(self, db_path: str = "pet_chat.db"):
        self.db_path = db_path
        self._create_tables()
    
    def _create_connection(self):
        return sqlite3.connect(self.db_path)
    
    def _create_tables(self):
        with self._create_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS attachments (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    mime_type TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            conn.commit()
    
    def generate_attachment_id(self, mime_type: str, context: Any) -> str:
        return f"atc_{uuid.uuid4().hex[:8]}"
    
    async def create_attachment(self, input: AttachmentCreateParams, context: Any) -> Attachment:
        """Create attachment metadata and return attachment object."""
        attachment_id = self.generate_attachment_id(input.mime_type, context)
        logger.info(f"Creating attachment with ID: {attachment_id}")

        # Create database record
        with self._create_connection() as conn:
            conn.execute(
                "INSERT INTO attachments (id, name, mime_type, size, data, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (attachment_id, input.name, input.mime_type, input.size, "", datetime.now().isoformat())
            )
            conn.commit()
            logger.info(f"Stored attachment in database with ID: {attachment_id}")
        
        if input.mime_type.startswith("image/"):
            return ImageAttachment(
                id=attachment_id,
                name=input.name,
                mime_type=input.mime_type,
                upload_url=None,  # Direct upload
                preview_url=f"data:{input.mime_type};base64,"
            )
        else:
            return FileAttachment(
                id=attachment_id,
                name=input.name,
                mime_type=input.mime_type,
                upload_url=None  # Direct upload
            )
    
    async def upload_attachment_data(self, attachment_id: str, data: bytes, context: Any) -> None:
        """Store the actual attachment data."""
        import base64
        base64_data = base64.b64encode(data).decode('utf-8')
        
        with self._create_connection() as conn:
            conn.execute(
                "UPDATE attachments SET data = ? WHERE id = ?",
                (base64_data, attachment_id)
            )
            conn.commit()
    
    async def delete_attachment(self, attachment_id: str, context: Any) -> None:
        """Delete attachment from database."""
        with self._create_connection() as conn:
            conn.execute("DELETE FROM attachments WHERE id = ?", (attachment_id,))
            conn.commit()

# =============================================================================
# PET ASSISTANT THREAD ITEM CONVERTER
# =============================================================================

class PetAssistantThreadItemConverter(ThreadItemConverter):
    """Custom converter for pet assistant that handles image attachments."""
    
    def __init__(self, store: Store):
        self.store = store
    
    async def attachment_to_message_content(self, attachment: Attachment):
        """Convert attachment to Agent SDK input format using ChatKit's native approach."""
        # Get the raw attachment data from our store
        with self.store._create_connection() as conn:
            cursor = conn.execute("SELECT data FROM attachments WHERE id = ?", (attachment.id,)).fetchone()
            base64_data = cursor[0] if cursor else ""
        
        # Create data URL for the attachment
        data_url = f"data:{attachment.mime_type};base64,{base64_data}"
        
        # Use proper ChatKit/Agent SDK types
        from openai.types.responses.response_input_image_param import ResponseInputImageParam
        from openai.types.responses.response_input_file_param import ResponseInputFileParam
        
        if isinstance(attachment, ImageAttachment):
            return ResponseInputImageParam(
                type="input_image",
                detail="auto",
                image_url=data_url,
            )
        else:
            # For non-image files, return as file parameter
            return ResponseInputFileParam(
                type="input_file",
                file_data=data_url,
                filename=attachment.name or "unknown",
            )

# =============================================================================
# FASTAPI APPLICATION
# =============================================================================

def create_app(data_store: Store) -> FastAPI:
    """Create FastAPI app with ChatKit server."""
    logger.info("Creating FastAPI application")
    
    app = FastAPI(
        title="Pet Food Assistant ChatKit Server",
        description="Simple ChatKit server following official docs",
        version="1.0.0"
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Frontend URLs
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    
    # Create attachment store and ChatKit server instance
    attachment_store = SimpleSQLiteAttachmentStore("pet_chat.db")
    chatkit_server = PetChatKitServer(data_store, attachment_store)
    
    @app.options("/chatkit")
    async def chatkit_options():
        """Handle CORS preflight requests."""
        return Response(status_code=200)
    
    @app.post("/chatkit")
    async def chatkit_endpoint(request: Request):
        """ChatKit endpoint following official documentation pattern."""
        logger.info("Received ChatKit request")
        
        # Extract context from headers
        user_id = request.headers.get("user-id")
        session_id = request.headers.get("session-id")
        username = request.headers.get("username", "benno")  # Default to "benno"
        
        # Create context dictionary
        context = {
            "user_id": user_id,
            "session_id": session_id,
            "username": username,
        }
        
        logger.info(f"Request context: {context}")
        
        try:
            # Use the official ChatKit server.process() method with context
            result = await chatkit_server.process(await request.body(), context)
            
            if isinstance(result, StreamingResult):
                logger.info("Returning streaming response")
                return StreamingResponse(result, media_type="text/event-stream")
            else:
                logger.info("Returning JSON response")
                return Response(content=result.json, media_type="application/json")
                
        except Exception as e:
            logger.error(f"Error processing ChatKit request: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy", "service": "pet-chatkit-server"}
    
    @app.post("/chatkit/attachments")
    async def upload_chatkit_attachment(request: Request):
        """Handle ChatKit direct attachment uploads."""
        logger.info("Received ChatKit attachment upload request")
        
        # Log all headers for debugging
        logger.info(f"Request headers: {dict(request.headers)}")
        
        # Extract context from headers
        user_id = request.headers.get("user-id")
        session_id = request.headers.get("session-id")
        username = request.headers.get("username", "benno")
        
        context = {
            "user_id": user_id,
            "session_id": session_id,
            "username": username,
        }
        
        try:
            # Check if this is a multipart form upload
            content_type = request.headers.get("content-type", "")
            if "multipart/form-data" in content_type:
                # Handle direct file upload
                form = await request.form()
                logger.info(f"Form data keys: {list(form.keys())}")
                logger.info(f"Form data: {dict(form)}")
                
                file = form.get("file")
                
                if not file:
                    raise HTTPException(status_code=400, detail="No file field in form data")
                
                # Generate a single attachment ID that we'll use consistently
                import uuid
                attachment_id = f"atc_{uuid.uuid4().hex[:8]}"
                logger.info(f"Generated attachment ID: {attachment_id}")
                
                # Read file data
                file_data = await file.read()
                
                # Create attachment metadata
                from chatkit.types import ImageAttachment, FileAttachment
                
                if file.content_type and file.content_type.startswith("image/"):
                    attachment = ImageAttachment(
                        id=attachment_id,
                        name=file.filename or "image",
                        mime_type=file.content_type,
                        upload_url=None,
                        preview_url=f"data:{file.content_type};base64,"
                    )
                else:
                    attachment = FileAttachment(
                        id=attachment_id,
                        name=file.filename or "file",
                        mime_type=file.content_type or "application/octet-stream",
                        upload_url=None
                    )
                
                # Store attachment metadata and data using the SAME ID
                from chatkit.types import AttachmentCreateParams
                create_params = AttachmentCreateParams(
                    name=attachment.name,
                    mime_type=attachment.mime_type,
                    size=len(file_data)
                )
                
                # Override the attachment store's ID generation to use our ID
                original_generate_id = attachment_store.generate_attachment_id
                attachment_store.generate_attachment_id = lambda mime_type, context: attachment_id
                
                try:
                    await attachment_store.create_attachment(create_params, context)
                    await attachment_store.upload_attachment_data(attachment_id, file_data, context)
                finally:
                    # Restore original ID generation method
                    attachment_store.generate_attachment_id = original_generate_id
                
                logger.info(f"Successfully uploaded ChatKit attachment {attachment_id}")
                return attachment.model_dump()
                
            else:
                # Handle legacy header-based approach
                attachment_id = (
                    request.headers.get("attachment-id") or
                    request.headers.get("attachment_id") or
                    request.headers.get("x-attachment-id") or
                    request.headers.get("X-Attachment-ID")
                )
                
                if not attachment_id:
                    import uuid
                    attachment_id = f"atc_{uuid.uuid4().hex[:8]}"
                    logger.info(f"Generated attachment ID: {attachment_id}")
                
                file_data = await request.body()
                logger.info(f"Received {len(file_data)} bytes of attachment data")
                
                await attachment_store.upload_attachment_data(attachment_id, file_data, context)
                
                logger.info(f"Successfully uploaded ChatKit attachment {attachment_id}")
                return {"status": "success", "attachment_id": attachment_id}
            
        except Exception as e:
            logger.error(f"Error uploading ChatKit attachment: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    logger.info("FastAPI application created successfully")
    return app

# =============================================================================
# MAIN EXECUTION
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    
    logger.info("Starting Pet ChatKit server")
    
    # Create SQLite store
    data_store = SimpleSQLiteStore("pet_chat.db")
    
    # Create FastAPI app
    app = create_app(data_store)
    
    # Run server
    logger.info("Server starting on http://localhost:9000")
    uvicorn.run(app, host="0.0.0.0", port=9000)
