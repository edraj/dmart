from datetime import datetime
from fastapi import status
from fastapi.responses import JSONResponse
from starlette.requests import Request
from models.core import User
from utils.jwt import JWTBearer
from utils.db import load
from utils.repository import _sys_update_model
from utils.settings import settings

class SessionActivityMiddleware:

    async def __call__(self, request: Request, call_next):
        user_model = None
        try:
            user_shortname = await JWTBearer().__call__(request)
            user_model: User = await load(
                settings.management_space,
                "users",
                user_shortname,
                User
            )
        except:
            # for guest users
            pass

        if(
            user_model and
            user_model.last_activity and
            (datetime.now() - user_model.last_activity).total_seconds() > 
            settings.session_inactivity_timeout
        ):
            response = JSONResponse(
                content={
                    "status": "failed",
                    "error": {
                        "type": "request",
                        "code": 422,
                        "message": "Session expired",
                        "info": None
                    }
                },
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
            )
            response.delete_cookie(key="auth_token")
            return response
        
        elif(user_model):
            await _sys_update_model(
                space_name=settings.management_space,
                subpath="users",
                meta=user_model,
                updates={
                    "last_activity": datetime.now()
                },
                branch_name=settings.management_space_branch
            )

        return await call_next(request)