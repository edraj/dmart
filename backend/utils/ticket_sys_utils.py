import models.api as api
from fastapi import status
from data_adapters.adapter import data_adapter as db
import models.core as core
from utils.internal_error_code import InternalErrorCode
from utils.settings import settings
from typing import Any


async def get_init_state_from_workflow(space_name: str, workflow_shortname: str):
    payload = await db.load_resource_payload(
        space_name=space_name,
        subpath="workflows",
        filename=workflow_shortname,
        class_type=core.Content,
    )

    if payload is None:
        raise api.Exception(
            status.HTTP_400_BAD_REQUEST,
            api.Error(
                type="request",
                code=InternalErrorCode.SHORTNAME_ALREADY_EXIST,
                message="Workflow not found",
            ),
        )

    return payload['initial_state'][0]['name']

async def set_init_state_for_record(record: core.Record, space_name: str, logged_in_user: str):
    workflow_attr = record.attributes
    workflow_shortname = workflow_attr["workflow_shortname"]

    _user_roles = await db.get_user_roles(logged_in_user)
    user_roles = _user_roles.keys()

    workflows_data: core.Content = await db.load(
        space_name=space_name,
        subpath="workflows",
        shortname=workflow_shortname,
        class_type=core.Content,
        user_shortname=logged_in_user,
    )

    if workflows_data is not None and workflows_data.payload is not None:
        workflows_payload: dict[str,Any]
        if isinstance(workflows_data.payload.body, dict):
            workflows_payload = workflows_data.payload.body
        else:
            payload = await db.load_resource_payload(
                space_name=space_name,
                subpath="workflows",
                filename=str(workflows_data.payload.body),
                class_type=core.Content,
            )
            workflows_payload = payload if payload else {}

        initial_state = None

        for state in workflows_payload["initial_state"]:
            if initial_state is None and "default" in state["roles"]:
                initial_state = state["name"]
            elif [role in user_roles for role in state["roles"]].count(True):
                initial_state = state["name"]
                break

        if initial_state is None:
            raise api.Exception(
                status.HTTP_400_BAD_REQUEST,
                api.Error(
                    type="request",
                    code=InternalErrorCode.NOT_ALLOWED,
                    message="The user does not have the required roles to create this ticket",
                ),
            )

        record.attributes = {
            **workflow_attr,
            "state": initial_state,
            "is_open": True,
        }
        return record

    raise api.Exception(
        status.HTTP_400_BAD_REQUEST,
        api.Error(
            type="request",
            code=InternalErrorCode.SHORTNAME_ALREADY_EXIST,
            message="This shortname already exists",
        ),
    )


async def set_init_state_from_record(
    ticket: core.Record, logged_in_user, space_name
):
    workflow_attr = ticket.attributes
    workflow_shortname = workflow_attr["workflow_shortname"]

    workflows_data = await db.load(
        space_name=space_name,
        subpath="workflows",
        shortname=workflow_shortname,
        class_type=core.Content,
        user_shortname=logged_in_user,
    )

    if workflows_data is not None and workflows_data.payload is not None:
        # file: fetch payload from file
        # sql: payload is already within the entry
        workflows_payload : dict[str, Any] = {}
        mypayload = workflows_data.payload.body
        if settings.active_data_db == "file" and isinstance(mypayload, str):
            payload = await db.load_resource_payload(
                space_name=space_name,
                subpath="workflows",
                filename=mypayload,
                class_type=core.Content,
            )
            workflows_payload = payload if payload else {}
        elif isinstance(mypayload, dict):
                workflows_payload = mypayload
        else:
            raise api.Exception(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                api.Error(
                    type="request",
                    code=InternalErrorCode.INVALID_DATA,
                    message=f"Invalid payload data {mypayload}",
                ),
            )



        ticket.attributes = {
            **workflow_attr,
            "state": workflows_payload["initial_state"],
        }
        return ticket

    raise api.Exception(
        status.HTTP_400_BAD_REQUEST,
        api.Error(
            type="request",
            code=InternalErrorCode.SHORTNAME_ALREADY_EXIST,
            message="This shortname already exists",
        ),
    )


def transite(states, current_state: str, action: str, user_roles):
    for state in states:
        if state["state"] == current_state:
            for next_state in state["next"]:
                if next_state["action"] == action:
                    for role in next_state["roles"]:
                        if role in user_roles:
                            return {"status": True, "message": next_state["state"]}
                    return {
                        "status": False,
                        "message": f"You don't have the permission to progress this ticket with action {action}",
                    }

    return {
        "status": False,
        "message": f"You can't progress from {current_state} using {action}",
    }


def post_transite(states, next_state: str, resolution: str):
    for state in states:
        if state["state"] == next_state:
            if "resolutions" in state:
                available_resolutions = [one for one in state["resolutions"]]
                if len(available_resolutions) == 0:
                    return {
                        "status": False,
                        "message": f"The state {next_state} does not have any resolutions defined",
                    }
                else:
                    if isinstance(available_resolutions[0], str):
                        if resolution in available_resolutions:
                            return {"status": True, "message": resolution}
                    else:
                        if resolution in [item['key'] for item in available_resolutions]:
                            return {"status": True, "message": resolution}

                return {
                    "status": False,
                    "message": f"The resolution {resolution} provided is not acceptable in state {next_state}",
                }
    return {
        "status": False,
        "message": f"Cannot fetch the next state {next_state} with resolution {resolution}",
    }


def check_open_state(states, current_state: str):
    for state in states:
        if state["state"] == current_state:
            return "next" in state

    return True
