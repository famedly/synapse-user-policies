import unittest
from unittest.mock import AsyncMock, Mock

from synapse.module_api import NOT_SPAM
from synapse.module_api.errors import Codes

from synapse_user_policies import UserPolicies

TYPES = {
    "@bot:x": "bot",
    "@bot2:x": "bot",
    "@sup:x": "support",
    "@anna:x": None,
    "@berta:x": None,
}


def make(members, config=None, third_party=()):
    """members: {user_id: membership}; user types from TYPES, others unknown.
    third_party: state keys (tokens) of m.room.third_party_invite events."""
    api = Mock()
    api.get_userinfo_by_id = AsyncMock(
        side_effect=lambda u: Mock(user_type=TYPES[u]) if u in TYPES else None
    )
    api.get_room_state = AsyncMock(
        return_value={
            ("m.room.member", u): Mock(state_key=u, content={"membership": m})
            for u, m in members.items()
        }
        | {
            ("m.room.third_party_invite", t): Mock(state_key=t, content={})
            for t in third_party
        }
    )
    return UserPolicies(UserPolicies.parse_config(config or {}), api), api


async def invite(mod, invitee):
    return await mod.user_may_invite("@bot:x", invitee, "!r:x")


async def invite_3pid(mod):
    return await mod.user_may_send_3pid_invite("@bot:x", "email", "a@b", "!r:x")


ALLOW_3PID = {"allow": {"invite_3pid": ["bot"]}}


class MemberCapTest(unittest.IsolatedAsyncioTestCase):
    ##= docs/requirements/user-policies.md#fm-pol-11
    ##= type=test
    ## The module MUST ensure that in a room at most as many users who are not of type bot have ever been invited or been members as max_default_members_per_room specifies.
    async def test_second_default_rejected_when_first_joined(self):
        mod, _ = make({"@bot:x": "join", "@anna:x": "join"})
        self.assertEqual(await invite(mod, "@berta:x"), Codes.FORBIDDEN)

    ##= docs/requirements/user-policies.md#fm-pol-11
    ##= type=test
    ## The module MUST ensure that in a room at most as many users who are not of type bot have ever been invited or been members as max_default_members_per_room specifies.
    async def test_second_default_rejected_when_first_invited(self):
        mod, _ = make({"@bot:x": "join", "@anna:x": "invite"})
        self.assertEqual(await invite(mod, "@berta:x"), Codes.FORBIDDEN)

    ##= docs/requirements/user-policies.md#fm-pol-11
    ##= type=test
    ## The module MUST ensure that in a room at most as many users who are not of type bot have ever been invited or been members as max_default_members_per_room specifies.
    async def test_left_and_banned_still_counted(self):
        for state in ("leave", "ban"):
            mod, _ = make({"@bot:x": "join", "@anna:x": state})
            self.assertEqual(await invite(mod, "@berta:x"), Codes.FORBIDDEN, state)

    ##= docs/requirements/user-policies.md#fm-pol-11
    ##= type=test
    ## The module MUST ensure that in a room at most as many users who are not of type bot have ever been invited or been members as max_default_members_per_room specifies.
    async def test_unknown_member_and_invitee_count_as_default(self):
        mod, _ = make({"@bot:x": "join", "@ghost:x": "join"})
        self.assertEqual(await invite(mod, "@berta:x"), Codes.FORBIDDEN)
        mod, _ = make({"@bot:x": "join", "@anna:x": "join"})
        self.assertEqual(await invite(mod, "@ghost:x"), Codes.FORBIDDEN)

    ##= docs/requirements/user-policies.md#fm-pol-11
    ##= type=test
    ## The module MUST ensure that in a room at most as many users who are not of type bot have ever been invited or been members as max_default_members_per_room specifies.
    async def test_reinviting_existing_member_not_counted_twice(self):
        mod, _ = make({"@bot:x": "join", "@anna:x": "invite"})
        self.assertEqual(await invite(mod, "@anna:x"), NOT_SPAM)

    ##= docs/requirements/user-policies.md#fm-pol-11
    ##= type=test
    ## Unless configured otherwise, max_default_members_per_room MUST equal 1.
    async def test_default_limit_is_one(self):
        mod, _ = make({})
        self.assertEqual(mod._config.max_default_members_per_room, 1)
        self.assertEqual(await invite(mod, "@anna:x"), NOT_SPAM)

    ##= docs/requirements/user-policies.md#fm-pol-11
    ##= type=test
    ## The module MUST ensure that in a room at most as many users who are not of type bot have ever been invited or been members as max_default_members_per_room specifies.
    async def test_configured_limit_two(self):
        mod, _ = make(
            {"@bot:x": "join", "@anna:x": "join"}, {"max_default_members_per_room": 2}
        )
        self.assertEqual(await invite(mod, "@berta:x"), NOT_SPAM)

    ##= docs/requirements/user-policies.md#fm-pol-11
    ##= type=test
    ## Multiple users of type bot MUST be allowed in a room.
    async def test_second_bot_allowed(self):
        mod, _ = make({"@bot:x": "join", "@anna:x": "join"})
        self.assertEqual(await invite(mod, "@bot2:x"), NOT_SPAM)

    ##= docs/requirements/user-policies.md#fm-pol-11
    ##= type=test
    ## The module MUST ensure that in a room at most as many users who are not of type bot have ever been invited or been members as max_default_members_per_room specifies.
    async def test_support_member_counted(self):
        mod, _ = make({"@bot:x": "join", "@sup:x": "join"})
        self.assertEqual(await invite(mod, "@berta:x"), Codes.FORBIDDEN)

    ##= docs/requirements/user-policies.md#fm-pol-11
    ##= type=test
    ## The module MUST ensure that in a room at most as many users who are not of type bot have ever been invited or been members as max_default_members_per_room specifies.
    async def test_limit_two_rejects_third_non_bot(self):
        mod, _ = make(
            {"@bot:x": "join", "@anna:x": "join", "@sup:x": "leave"},
            {"max_default_members_per_room": 2},
        )
        self.assertEqual(await invite(mod, "@berta:x"), Codes.FORBIDDEN)

    ##= docs/requirements/user-policies.md#fm-pol-11
    ##= type=test
    ## The limit MUST also apply to invitations by email address or phone number, whose invitee counts as a user who is not of type bot.
    async def test_3pid_invite_capped(self):
        mod, _ = make({"@bot:x": "join"}, ALLOW_3PID)
        self.assertEqual(await invite_3pid(mod), NOT_SPAM)
        mod, _ = make({"@bot:x": "join", "@anna:x": "invite"}, ALLOW_3PID)
        self.assertEqual(await invite_3pid(mod), Codes.FORBIDDEN)

    ##= docs/requirements/user-policies.md#fm-pol-11
    ##= type=test
    ## Every m.room.third_party_invite in the room MUST count as one user who is not of type bot, also after it has been redeemed.
    async def test_third_party_invite_counted(self):
        mod, _ = make({"@bot:x": "join"}, ALLOW_3PID, third_party=["tok"])
        self.assertEqual(await invite(mod, "@anna:x"), Codes.FORBIDDEN)
        self.assertEqual(await invite_3pid(mod), Codes.FORBIDDEN)
        self.assertEqual(await invite(mod, "@bot2:x"), NOT_SPAM)
