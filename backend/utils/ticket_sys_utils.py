import models.api as api
from fastapi import status
from utils.data_database import data_adapter as db
import models.core as core
from utils.access_control import access_control
from utils.internal_error_code import InternalErrorCode


async def set_init_state_from_request(ticket: api.Request, logged_in_user):
    workflow_attr = ticket.records[0].attributes
    workflow_shortname = workflow_attr["workflow_shortname"]

    _user_roles = await access_control.get_user_roles(logged_in_user)
    user_roles = _user_roles.keys()

    workflows_data = await db.load(
        space_name=ticket.space_name,
        subpath="workflows",
        shortname=workflow_shortname,
        class_type=core.Content,
        user_shortname=logged_in_user,
    )

    if workflows_data is not None and workflows_data.payload is not None:
        workflows_payload = db.load_resource_payload(
            space_name=ticket.space_name,
            subpath="workflows",
            filename=str(workflows_data.payload.body),
            class_type=core.Content,
        )

        initial_state = None
        for state in workflows_payload["initial_state"]:
            if initial_state is None and "default" in state["roles"]:
                initial_state = state["name"]
            elif [role in user_roles for role in state["roles"]].count(True):
                initial_state = state["name"]
                break

        ticket.records[0].attributes = {
            **workflow_attr,
            "state": initial_state,
            "is_open": True,
        }
        return ticket.records[0]

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
        workflows_payload = db.load_resource_payload(
            space_name=space_name,
            subpath="workflows",
            filename=str(workflows_data.payload.body),
            class_type=core.Content,
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
                if resolution in available_resolutions:
                    return {"status": True, "message": resolution}
                else:
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
