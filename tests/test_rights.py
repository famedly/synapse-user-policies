import unittest
from unittest.mock import AsyncMock, Mock

from synapse.module_api import NOT_SPAM
from synapse.module_api.errors import Codes
from synapse.types import RoomAlias

from synapse_user_policies import UserPolicies

ALIAS = RoomAlias.from_string("#x:example.org")

# name -> (kwargs, action key in allow)
CALLS = {
    "user_may_create_room": ({"room_config": {}}, "create_room"),
    "user_may_invite": ({"invitee": "@b:x", "room_id": "!r:x"}, "invite"),
    "user_may_send_3pid_invite": (
        {"medium": "email", "address": "a@b", "room_id": "!r:x"},
        "invite_3pid",
    ),
    "user_may_create_room_alias": ({"room_alias": ALIAS}, "create_room_alias"),
    "user_may_publish_room": ({"room_id": "!r:x"}, "publish_room"),
    "user_may_send_state_event": (
        {
            "room_id": "!r:x",
            "event_type": "m.room.name",
            "state_key": "",
            "content": {},
        },
        "send_state_event",
    ),
    "user_may_join_room": (
        {"room_id": "!r:x", "is_invited": False},
        "join_uninvited_room",
    ),
}
# The first positional parameter's name differs per callback.
FIRST = {"user_may_invite": "inviter", "user_may_send_3pid_invite": "inviter"}


def make(config=None, user_type="bot", found=True):
    api = Mock()
    api.get_userinfo_by_id = AsyncMock(
        return_value=Mock(user_type=user_type) if found else None
    )
    api.get_room_state = AsyncMock(return_value={})
    return UserPolicies(UserPolicies.parse_config(config or {}), api), api


async def call(mod, name, **override):
    kwargs, _ = CALLS[name]
    kwargs = {**kwargs, **override}
    return await getattr(mod, name)(**{FIRST.get(name, "user_id"): "@a:x"}, **kwargs)


class RightsTest(unittest.IsolatedAsyncioTestCase):
    ##= docs/requirements/user-policies.md#fm-pol-1
    ##= type=test
    ## An account without user_type MUST count as type default.
    ##= docs/requirements/user-policies.md#fm-pol-2
    ##= type=test
    ## If an action is missing from allow, it MUST be forbidden for all user types.
    ##= docs/requirements/user-policies.md#fm-pol-2
    ##= type=test
    ## If the module rejects an action, Synapse MUST respond with 403 and the error code M_FORBIDDEN.
    async def test_default_denied(self):
        for name in CALLS:
            mod, _ = make(user_type=None)
            self.assertEqual(await call(mod, name), Codes.FORBIDDEN, name)

    ##= docs/requirements/user-policies.md#fm-pol-1
    ##= type=test
    ## The module MUST determine a user's rights exclusively from the Synapse field user_type of their account.
    ##= docs/requirements/user-policies.md#fm-pol-3
    ##= type=test
    ## The module MUST check the action create_room when a room is created and when a room is upgraded.
    ##= docs/requirements/user-policies.md#fm-pol-3
    ##= type=test
    ## The module MUST check the action invite on every local invitation, including invitations in the invite field of createRoom and via the state endpoint with m.room.member.
    ##= docs/requirements/user-policies.md#fm-pol-3
    ##= type=test
    ## The module MUST check the action invite_3pid on invitations by email address or phone number.
    ##= docs/requirements/user-policies.md#fm-pol-3
    ##= type=test
    ## The module MUST check the action create_room_alias when an alias is created, including via room_alias_name in createRoom.
    ##= docs/requirements/user-policies.md#fm-pol-3
    ##= type=test
    ## The module MUST check the action publish_room when a room is published in the room directory.
    ##= docs/requirements/user-policies.md#fm-pol-3
    ##= type=test
    ## The module MUST check the action send_state_event on every PUT to a room's state endpoint.
    ##= docs/requirements/user-policies.md#fm-pol-3
    ##= type=test
    ## The module MUST check the action join_uninvited_room on every join to a room the user has not been invited to.
    async def test_bot_allowed(self):
        for name, (_, action) in CALLS.items():
            # create_room_alias and publish_room are denied to everyone by default.
            cfg = {"allow": {action: ["bot"]}}
            mod, _ = make(cfg)
            self.assertEqual(await call(mod, name), NOT_SPAM, name)

    ##= docs/requirements/user-policies.md#fm-pol-2
    ##= type=test
    ## If the module cannot determine the user type of an account, it MUST reject the action.
    async def test_unknown_user_denied(self):
        # Even where the config would allow every type, including default.
        cfg = {"allow": {a: ["bot", "default"] for _, a in CALLS.values()}}
        for name in CALLS:
            mod, _ = make(cfg, found=False)
            self.assertEqual(await call(mod, name), Codes.FORBIDDEN, name)

    async def test_bot_denied_for_alias_and_publish_by_default(self):
        for name in ("user_may_create_room_alias", "user_may_publish_room"):
            mod, _ = make()
            self.assertEqual(await call(mod, name), Codes.FORBIDDEN, name)

    ##= docs/requirements/user-policies.md#fm-pol-4
    ##= type=test
    ## The module MUST NOT restrict login, logout, changing display name and avatar, accepting an invitation, reading and sending messages, or exchanging E2EE keys.
    async def test_join_when_invited_not_gated(self):
        mod, _ = make(user_type=None)
        self.assertEqual(
            await call(mod, "user_may_join_room", is_invited=True), NOT_SPAM
        )

    async def test_always_allowed_state_event(self):
        mod, _ = make({"always_allowed_state_events": ["m.room.topic"]}, user_type=None)
        self.assertEqual(
            await call(mod, "user_may_send_state_event", event_type="m.room.topic"),
            NOT_SPAM,
        )
        self.assertEqual(
            await call(
                mod, "user_may_send_state_event", event_type="m.room.power_levels"
            ),
            Codes.FORBIDDEN,
        )

    async def test_alias_pattern(self):
        mod, _ = make(
            {
                "allow": {"create_room_alias": ["bot"]},
                "alias_pattern": "^#[a-z0-9]{24}:",
            }
        )
        good = RoomAlias.from_string("#" + "a1" * 12 + ":example.org")
        bad = RoomAlias.from_string("#mueller-anna:x")
        self.assertEqual(
            await call(mod, "user_may_create_room_alias", room_alias=good), NOT_SPAM
        )
        self.assertEqual(
            await call(mod, "user_may_create_room_alias", room_alias=bad),
            Codes.FORBIDDEN,
        )

    async def test_registers_only_expected_callbacks(self):
        _, api = make()
        api.register_spam_checker_callbacks.assert_called_once()
        self.assertEqual(
            set(api.register_spam_checker_callbacks.call_args.kwargs),
            set(CALLS) | {"federated_user_may_invite"},
        )

    ##= docs/requirements/user-policies.md#fm-pol-7
    ##= type=test
    ## The module MUST reject every invitation from another homeserver unless allow_federated_invites is true.
    async def test_federated_invite(self):
        mod, _ = make()
        self.assertEqual(await mod.federated_user_may_invite(Mock()), Codes.FORBIDDEN)
        mod, _ = make({"allow_federated_invites": True})
        self.assertEqual(await mod.federated_user_may_invite(Mock()), NOT_SPAM)
