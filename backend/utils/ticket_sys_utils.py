import models.api as api
from fastapi import status
from models.enums import ResourceType
from utils.data_repo import data_adapter as db
import models.core as core
from utils.internal_error_code import InternalErrorCode
from utils.access_control import access_control

async def set_ticket_init_state(dto: core.EntityDTO, ticket: core.Ticket) -> core.Ticket:
# async def set_init_state_from_request(ticket: api.Request, branch_name, logged_in_user):
    # workflow_attr = ticket.records[0].attributes
    # workflow_shortname = workflow_attr["workflow_shortname"]
    if not dto.user_shortname:
        raise Exception("Missing user_shortname in the EntityDTO")

    user_roles_names = list((await access_control.get_user_roles(dto.user_shortname)).keys())
    # user_roles = _user_roles.keys()

    workflow_dto = core.EntityDTO(
        **dto.model_dump(include={"space_name", "user_shortname"}),
        shortname=ticket.workflow_shortname,
        resource_type=ResourceType.content,
        subpath="workflows"
    )
    workflows_data: core.Meta = await db.load(workflow_dto)

    if workflows_data.payload is None:
        raise api.Exception(
            status.HTTP_400_BAD_REQUEST,
            api.Error(
                type="request",
                code=InternalErrorCode.SHORTNAME_ALREADY_EXIST,
                message="This shortname already exists",
            ),
        )

    workflows_payload = await db.load_resource_payload(workflow_dto)
    if "initial_state" not in workflows_payload or not isinstance(workflows_payload["initial_state"], list):
        raise api.Exception(
            status.HTTP_400_BAD_REQUEST,
            api.Error(
                type="request",
                code=InternalErrorCode.SHORTNAME_ALREADY_EXIST,
                message="This shortname already exists",
            ),
        )

    initial_state = None
    for state in workflows_payload["initial_state"]:
        if initial_state is None and "default" in state["roles"]:
            initial_state = state["name"]
        elif [role in user_roles_names for role in state["roles"]].count(True):
            initial_state = state["name"]
            break

    
    ticket.state = initial_state
    ticket.is_open = True
    
    return ticket

    


# async def set_init_state_from_record(
#     ticket: core.Record, branch_name, logged_in_user, space_name
# ):
#     workflow_attr = ticket.attributes
#     workflow_shortname = workflow_attr["workflow_shortname"]

#     workflows_data = await db.load(
#         space_name=space_name,
#         subpath="workflows",
#         shortname=workflow_shortname,
#         class_type=core.Content,
#         user_shortname=logged_in_user,
#         branch_name=branch_name,
#     )

#     if workflows_data is not None and workflows_data.payload is not None:
#         workflows_payload = db.load_resource_payload(
#             space_name=space_name,
#             subpath="workflows",
#             filename=str(workflows_data.payload.body),
#             class_type=core.Content,
#             branch_name=branch_name,
#         )
#         ticket.attributes = {
#             **workflow_attr,
#             "state": workflows_payload["initial_state"],
#         }
#         return ticket

#     raise api.Exception(
#         status.HTTP_400_BAD_REQUEST,
#         api.Error(
#             type="request",
#             code=InternalErrorCode.SHORTNAME_ALREADY_EXIST,
#             message="This shortname already exists",
#         ),
#     )


def transite(states, action: str, user_roles, current_state: str | None = None):
    if not current_state:
        return {
            "status": False,
            "message": f"You can't progress from {current_state} using {action}",
        }
        
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
