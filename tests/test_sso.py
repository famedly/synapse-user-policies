import asyncio
import re
import unittest
from unittest.mock import AsyncMock, Mock

from synapse.types import UserID

from synapse_user_policies import RandomLocalpartMapping, UserPolicies

UUID4 = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


class RandomLocalpartMappingTest(unittest.TestCase):
    def setUp(self):
        self.provider = RandomLocalpartMapping(
            RandomLocalpartMapping.parse_config({}), Mock()
        )
        self.userinfo = {
            "sub": "123",
            "email": "a@example.org",
            "email_verified": True,
            "name": "Ann",
            "picture": "https://x/p",
        }

    ##= docs/requirements/user-policies.md#fm-pol-30
    ##= type=test
    ## For a new account, the mapping provider MUST return a localpart that is the lower-case text form of a random UUIDv4.
    ##= docs/requirements/user-policies.md#fm-pol-30
    ##= type=test
    ## The mapping provider MUST NOT let the user confirm or choose the localpart.
    ##= docs/requirements/user-policies.md#fm-pol-30
    ##= type=test
    ## For a new account, the mapping provider MUST take over the claim name of the identity provider as the display name, if it is present.
    ##= docs/requirements/user-policies.md#fm-pol-30
    ##= type=test
    ## The mapping provider MUST NOT take over an avatar or email addresses from the identity provider.
    def test_random_localpart_and_name_only(self):
        a = asyncio.run(self.provider.map_user_attributes(self.userinfo, {}, 0))
        b = asyncio.run(self.provider.map_user_attributes(self.userinfo, {}, 1))
        self.assertRegex(a["localpart"], UUID4)
        self.assertNotEqual(a["localpart"], b["localpart"])
        self.assertEqual(
            {k: v for k, v in a.items() if k != "localpart"},
            {
                "confirm_localpart": False,
                "display_name": "Ann",
                "picture": None,
                "emails": [],
            },
        )

    def test_no_name_claim(self):
        # Apple's id_token has no name.
        a = asyncio.run(self.provider.map_user_attributes({"sub": "123"}, {}, 0))
        self.assertIsNone(a["display_name"])
        a = asyncio.run(
            self.provider.map_user_attributes({"sub": "1", "name": "  "}, {}, 0)
        )
        self.assertIsNone(a["display_name"])

    ##= docs/requirements/user-policies.md#fm-pol-30
    ##= type=test
    ## The mapping provider MUST use the claim sub of the identity provider as the remote user ID.
    def test_remote_user_id_is_sub(self):
        self.assertEqual(self.provider.get_remote_user_id(self.userinfo), "123")

    def test_no_config(self):
        with self.assertRaises(ValueError):
            RandomLocalpartMapping.parse_config(
                {"localpart_template": "{{ user.email }}"}
            )


def make_policies(erased=True, media=("m1", "m2", "m3")):
    store = Mock()
    store.is_user_erased = AsyncMock(return_value=erased)

    async def paginate(start, limit, user_id):
        return [Mock(media_id=m) for m in media[start : start + 2]], len(media)

    store.get_local_media_by_user_paginate = AsyncMock(side_effect=paginate)
    store.get_external_ids_by_user = AsyncMock(return_value=[("oidc-google", "123")])
    store.remove_user_external_id = AsyncMock()
    repo = Mock()
    repo.delete_local_media_ids = AsyncMock(return_value=([], 0))
    api = Mock()
    api._hs.get_datastores.return_value.main = store
    api._hs.get_media_repository.return_value = repo

    return UserPolicies(UserPolicies.parse_config({}), api), repo, store


class MediaPurgeTest(unittest.TestCase):
    ##= docs/requirements/user-policies.md#fm-pol-31
    ##= type=test
    ## When an account of the homeserver is deactivated with erase, the module MUST delete all media the account uploaded.
    ##= docs/requirements/user-policies.md#fm-pol-31
    ##= type=test
    ## When an account of the homeserver is deactivated with erase, the module MUST remove the account's external IDs.
    ##= docs/requirements/user-policies.md#fm-pol-31
    ##= type=test
    ## This MUST apply to deactivation by a server admin and by the user.
    def test_erased_user_loses_all_media_and_external_ids(self):
        for by_admin in (True, False):
            mod, repo, store = make_policies()
            asyncio.run(mod.on_user_deactivation_status_changed("@u:x", True, by_admin))
            repo.delete_local_media_ids.assert_awaited_once_with(["m1", "m2", "m3"])
            store.remove_user_external_id.assert_awaited_once_with(
                "oidc-google", "123", "@u:x"
            )

    def test_keeps_media_without_erase_or_on_reactivation(self):
        for erased, deactivated in ((False, True), (True, False)):
            mod, repo, store = make_policies(erased=erased)
            asyncio.run(
                mod.on_user_deactivation_status_changed("@u:x", deactivated, True)
            )
            repo.delete_local_media_ids.assert_not_awaited()
            store.remove_user_external_id.assert_not_awaited()

    def test_no_media(self):
        mod, repo, _ = make_policies(media=())
        asyncio.run(mod.on_user_deactivation_status_changed("@u:x", True, False))
        repo.delete_local_media_ids.assert_not_awaited()


class NoLocalpartDisplayNameTest(unittest.TestCase):
    def run_registration(self, user_id, displayname):
        mod, _, _ = make_policies()
        api = mod._api
        api.get_profile_for_user = AsyncMock(
            return_value=Mock(display_name=displayname)
        )
        api.set_displayname = AsyncMock()
        asyncio.run(mod.on_user_registration(user_id))
        return api

    ##= docs/requirements/user-policies.md#fm-pol-30
    ##= type=test
    ## When an account is created whose display name equals its localpart, the module MUST remove the display name.
    def test_localpart_as_display_name_is_removed(self):
        uid = "@0f5e-uuid:example.org"
        api = self.run_registration(uid, "0f5e-uuid")
        api.get_profile_for_user.assert_awaited_once_with("0f5e-uuid")
        # Synapse's profile handler stores an empty display name as none.
        api.set_displayname.assert_awaited_once_with(UserID.from_string(uid), "")

    def test_real_name_stays(self):
        for name in ("Ann", None, ""):
            api = self.run_registration("@0f5e-uuid:example.org", name)
            api.set_displayname.assert_not_awaited()
