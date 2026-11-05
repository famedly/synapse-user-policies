import re
from collections.abc import Mapping
from dataclasses import dataclass

from synapse.module_api.errors import ConfigError

ACTIONS = (
    "create_room",
    "invite",
    "invite_3pid",
    "create_room_alias",
    "publish_room",
    "send_state_event",
    "join_uninvited_room",
)

##= docs/requirements/user-policies.md#fm-pol-5
## Unless configured otherwise, allow MUST permit the actions create_room, invite, send_state_event and join_uninvited_room only for type bot.
##= docs/requirements/user-policies.md#fm-pol-5
## Unless configured otherwise, allow MUST permit the actions invite_3pid, create_room_alias and publish_room for no user type.
_DEFAULT_ALLOW = {
    "create_room": ["bot"],
    "invite": ["bot"],
    "invite_3pid": [],
    "send_state_event": ["bot"],
    "join_uninvited_room": ["bot"],
    "create_room_alias": [],
    "publish_room": [],
}

_KEYS = {
    "allow",
    "always_allowed_state_events",
    "alias_pattern",
    "max_default_members_per_room",
    "allow_federated_invites",
}


@dataclass(frozen=True)
class Config:
    allow: Mapping[str, frozenset]
    always_allowed_state_events: frozenset
    alias_pattern: re.Pattern | None
    max_default_members_per_room: int
    allow_federated_invites: bool


def _str_list(value, what: str) -> frozenset:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ConfigError(f"{what} must be a list of strings")
    return frozenset(value)


##= docs/requirements/user-policies.md#fm-pol-6
## If the configuration contains an unknown action, an unknown key or a value of the wrong type, Synapse MUST NOT start.
def parse_config(raw: dict) -> Config:
    if not isinstance(raw, dict):
        raise ConfigError("config must be a mapping")
    if unknown := set(raw) - _KEYS:
        raise ConfigError(f"unknown config keys: {sorted(unknown)}")

    user_allow = raw.get("allow", {})
    if not isinstance(user_allow, dict):
        raise ConfigError("allow must be a mapping")
    if unknown := set(user_allow) - set(ACTIONS):
        raise ConfigError(f"unknown actions in allow: {sorted(unknown)}")
    # A supplied entry replaces only the action it names.
    allow = {a: frozenset(d) for a, d in _DEFAULT_ALLOW.items()}
    for action, types in user_allow.items():
        allow[action] = _str_list(types, f"allow.{action}")

    events = _str_list(
        raw.get("always_allowed_state_events", []), "always_allowed_state_events"
    )

    pattern = raw.get("alias_pattern")
    if pattern is not None:
        if not isinstance(pattern, str):
            raise ConfigError("alias_pattern must be a string or null")
        try:
            pattern = re.compile(pattern)
        except re.error as e:
            raise ConfigError(f"alias_pattern is not a valid regex: {e}")

    max_members = raw.get("max_default_members_per_room", 1)
    if (
        isinstance(max_members, bool)
        or not isinstance(max_members, int)
        or max_members < 1
    ):
        raise ConfigError("max_default_members_per_room must be an integer >= 1")

    ##= docs/requirements/user-policies.md#fm-pol-7
    ## Unless configured otherwise, allow_federated_invites MUST be false.
    federated = raw.get("allow_federated_invites", False)
    if not isinstance(federated, bool):
        raise ConfigError("allow_federated_invites must be a boolean")

    return Config(allow, events, pattern, max_members, federated)


##= docs/requirements/user-policies.md#fm-pol-2
## An action MUST be allowed only for the user types listed for this action in the configuration allow.
##= docs/requirements/user-policies.md#fm-pol-2
## If an action is missing from allow, it MUST be forbidden for all user types.
def allowed(config: Config, action: str, user_type: str | None) -> bool:
    return (user_type or "default") in config.allow.get(action, frozenset())
