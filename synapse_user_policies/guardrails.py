# event type -> predicate that is true when the content violates FM-POL-10.
_STATE_RULES = {
    "m.room.join_rules": lambda c: c.get("join_rule") != "invite",
    "m.room.history_visibility": lambda c: (
        c.get("history_visibility") == "world_readable"
    ),
    "m.room.guest_access": lambda c: c.get("guest_access") == "can_join",
    "m.room.encryption": lambda c: c.get("algorithm") != "m.megolm.v1.aes-sha2",
}


##= docs/requirements/user-policies.md#fm-pol-10
## The join rule of a room MUST always be invite.
##= docs/requirements/user-policies.md#fm-pol-10
## The history visibility of a room MUST NOT be world_readable.
##= docs/requirements/user-policies.md#fm-pol-10
## The guest access of a room MUST NOT be can_join.
##= docs/requirements/user-policies.md#fm-pol-10
## The encryption algorithm of a room MUST be m.megolm.v1.aes-sha2.
def state_event_violation(event_type: str, content: dict) -> bool:
    rule = _STATE_RULES.get(event_type)
    return bool(rule and rule(content))


##= docs/requirements/user-policies.md#fm-pol-10
## Every room MUST be encrypted from its creation.
##= docs/requirements/user-policies.md#fm-pol-10
## The module MUST reject every room creation and every event that would violate one of these conditions.
def check_create_room(request_content: dict) -> str | None:
    """Return a rejection reason, or None. Mutates request_content: forces guest_access forbidden."""
    if (
        request_content.get("visibility") == "public"
        or request_content.get("preset") == "public_chat"
    ):
        return "Public rooms are not allowed"
    initial_state = request_content.setdefault("initial_state", [])
    types = set()
    for entry in initial_state:
        # Only the empty state_key matters for these room-level types.
        if entry.get("state_key", "") != "":
            continue
        types.add(entry.get("type"))
        if state_event_violation(entry.get("type"), entry.get("content", {})):
            return f"{entry['type']} violates the room guardrails"
    if "m.room.encryption" not in types:
        return "Rooms must be encrypted from creation"
    if "m.room.guest_access" not in types:
        # Explicit initial_state overrides the preset (private_chat would give can_join).
        initial_state.append(
            {
                "type": "m.room.guest_access",
                "state_key": "",
                "content": {"guest_access": "forbidden"},
            }
        )
    return None
