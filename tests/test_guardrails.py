import unittest
from unittest.mock import AsyncMock, Mock

from synapse.module_api.errors import Codes, SynapseError

from synapse_user_policies import UserPolicies
from synapse_user_policies.guardrails import check_create_room

ENC = {
    "type": "m.room.encryption",
    "state_key": "",
    "content": {"algorithm": "m.megolm.v1.aes-sha2"},
}


ENC_EVENT = ("m.room.encryption", {"algorithm": "m.megolm.v1.aes-sha2"})


def state(event_type, content):
    return {"type": event_type, "state_key": "", "content": content}


def request(**kw):
    kw.setdefault("preset", "private_chat")
    kw["initial_state"] = [ENC, *kw.get("initial_state", [])]
    return kw


def policies():
    return UserPolicies(
        UserPolicies.parse_config({}), Mock(get_userinfo_by_id=AsyncMock())
    )


def event(event_type, content, is_state=True):
    return Mock(
        type=event_type, state_key="", content=content, is_state=lambda: is_state
    )


class CheckCreateRoomTest(unittest.TestCase):
    ##= docs/requirements/user-policies.md#fm-pol-10
    ##= type=test
    ## The join rule of a room MUST always be invite.
    ##= docs/requirements/user-policies.md#fm-pol-10
    ##= type=test
    ## The history visibility of a room MUST NOT be world_readable.
    ##= docs/requirements/user-policies.md#fm-pol-10
    ##= type=test
    ## The guest access of a room MUST NOT be can_join.
    ##= docs/requirements/user-policies.md#fm-pol-10
    ##= type=test
    ## Every room MUST be encrypted from its creation.
    ##= docs/requirements/user-policies.md#fm-pol-10
    ##= type=test
    ## The encryption algorithm of a room MUST be m.megolm.v1.aes-sha2.
    ##= docs/requirements/user-policies.md#fm-pol-10
    ##= type=test
    ## The module MUST reject every room creation and every event that would violate one of these conditions.
    def test_violations(self):
        cases = {
            "public visibility": request(visibility="public"),
            "public_chat preset": request(preset="public_chat"),
            "public join rule": request(
                initial_state=[state("m.room.join_rules", {"join_rule": "public"})]
            ),
            "world_readable": request(
                initial_state=[
                    state(
                        "m.room.history_visibility",
                        {"history_visibility": "world_readable"},
                    )
                ]
            ),
            "guest can_join": request(
                initial_state=[
                    state("m.room.guest_access", {"guest_access": "can_join"})
                ]
            ),
            "no encryption": {"preset": "private_chat"},
            "empty encryption": {
                "preset": "private_chat",
                "initial_state": [state("m.room.encryption", {})],
            },
            "encryption none": {
                "preset": "private_chat",
                "initial_state": [state("m.room.encryption", {"algorithm": "none"})],
            },
        }
        for name, content in cases.items():
            with self.subTest(name):
                self.assertIsNotNone(check_create_room(content))

    ##= docs/requirements/user-policies.md#fm-pol-10
    ##= type=test
    def test_private_chat_gets_guest_access_forbidden(self):
        content = request()
        self.assertIsNone(check_create_room(content))
        self.assertIn(
            state("m.room.guest_access", {"guest_access": "forbidden"}),
            content["initial_state"],
        )

    def test_valid_request_passes(self):
        self.assertIsNone(check_create_room(request()))


class CallbackTest(unittest.IsolatedAsyncioTestCase):
    ##= docs/requirements/user-policies.md#fm-pol-10
    ##= type=test
    ## The guardrails MUST apply to users of every type, including bot.
    async def test_applies_to_admins(self):
        with self.assertRaises(SynapseError) as cm:
            await policies().on_create_room(
                Mock(), {"preset": "public_chat"}, is_requester_admin=True
            )
        self.assertEqual(
            (cm.exception.code, cm.exception.errcode), (403, Codes.FORBIDDEN)
        )

    async def test_on_create_room_accepts_valid(self):
        await policies().on_create_room(Mock(), request(), False)

    ##= docs/requirements/user-policies.md#fm-pol-10
    ##= type=test
    async def test_check_event_allowed(self):
        p = policies()
        for ev in (
            event("m.room.join_rules", {"join_rule": "public"}),
            event(
                "m.room.history_visibility", {"history_visibility": "world_readable"}
            ),
            event("m.room.guest_access", {"guest_access": "can_join"}),
            event("m.room.encryption", {}),
            event("m.room.encryption", {"algorithm": "none"}),
        ):
            self.assertEqual(await p.check_event_allowed(ev, {}), (False, None))
        self.assertEqual(
            await p.check_event_allowed(
                event("m.room.message", {"body": "x"}, is_state=False), {}
            ),
            (True, None),
        )
        self.assertEqual(
            await p.check_event_allowed(
                event("m.room.join_rules", {"join_rule": "invite"}), {}
            ),
            (True, None),
        )
        self.assertEqual(
            await p.check_event_allowed(event(*ENC_EVENT), {}),
            (True, None),
        )
