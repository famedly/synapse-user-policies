import unittest

from synapse.module_api.errors import ConfigError

from synapse_user_policies.config import allowed, parse_config


class ConfigTest(unittest.TestCase):
    ##= docs/requirements/user-policies.md#fm-pol-5
    ##= type=test
    ## Unless configured otherwise, allow MUST permit the actions create_room, invite, send_state_event and join_uninvited_room only for type bot.
    ##= docs/requirements/user-policies.md#fm-pol-5
    ##= type=test
    ## Unless configured otherwise, allow MUST permit the actions invite_3pid, create_room_alias and publish_room for no user type.
    ##= docs/requirements/user-policies.md#fm-pol-7
    ##= type=test
    ## Unless configured otherwise, allow_federated_invites MUST be false.
    def test_defaults(self):
        cfg = parse_config({})
        for a in (
            "create_room",
            "invite",
            "send_state_event",
            "join_uninvited_room",
        ):
            self.assertEqual(cfg.allow[a], frozenset({"bot"}), a)
        for a in ("invite_3pid", "create_room_alias", "publish_room"):
            self.assertEqual(cfg.allow[a], frozenset(), a)
        self.assertEqual(cfg.always_allowed_state_events, frozenset())
        self.assertIsNone(cfg.alias_pattern)
        self.assertEqual(cfg.max_default_members_per_room, 1)
        self.assertFalse(cfg.allow_federated_invites)

    def test_partial_allow_keeps_other_defaults(self):
        cfg = parse_config({"allow": {"invite": ["bot", "default"]}})
        self.assertTrue(allowed(cfg, "invite", "bot"))
        self.assertTrue(allowed(cfg, "invite", None))
        self.assertTrue(allowed(cfg, "create_room", "bot"))
        self.assertFalse(allowed(cfg, "create_room", None))

    ##= docs/requirements/user-policies.md#fm-pol-2
    ##= type=test
    ## If an action is missing from allow, it MUST be forbidden for all user types.
    def test_missing_action_forbidden_for_all(self):
        cfg = parse_config({})
        self.assertFalse(allowed(cfg, "unknown", "bot"))

    ##= docs/requirements/user-policies.md#fm-pol-2
    ##= type=test
    ## An action MUST be allowed only for the user types listed for this action in the configuration allow.
    def test_default_type_is_none(self):
        cfg = parse_config({})
        self.assertFalse(allowed(cfg, "create_room", None))
        self.assertTrue(allowed(cfg, "create_room", "bot"))
        self.assertFalse(allowed(cfg, "create_room", "support"))

    ##= docs/requirements/user-policies.md#fm-pol-6
    ##= type=test
    ## If the configuration contains an unknown action, an unknown key or a value of the wrong type, Synapse MUST NOT start.
    def test_invalid_config_rejected(self):
        cases = {
            "unknown key": {"nope": 1},
            "unknown action": {"allow": {"nope": ["bot"]}},
            "allow not a dict": {"allow": ["bot"]},
            "action value not a list": {"allow": {"invite": "bot"}},
            "type not a str": {"allow": {"invite": [1]}},
            "events not a list": {"always_allowed_state_events": "m.room.name"},
            "event not a str": {"always_allowed_state_events": [1]},
            "max zero": {"max_default_members_per_room": 0},
            "max bool": {"max_default_members_per_room": True},
            "max str": {"max_default_members_per_room": "1"},
            "alias_pattern int": {"alias_pattern": 5},
            "invalid regex": {"alias_pattern": "("},
            "federated str": {"allow_federated_invites": "true"},
        }
        for name, raw in cases.items():
            with self.subTest(name), self.assertRaises(ConfigError):
                parse_config(raw)

    def test_valid_overrides(self):
        cfg = parse_config(
            {
                "allow": {"publish_room": ["bot"]},
                "always_allowed_state_events": ["m.room.name"],
                "alias_pattern": "#x:.*",
                "max_default_members_per_room": 2,
                "allow_federated_invites": True,
            }
        )
        self.assertTrue(allowed(cfg, "publish_room", "bot"))
        self.assertEqual(cfg.always_allowed_state_events, frozenset({"m.room.name"}))
        self.assertTrue(cfg.alias_pattern.fullmatch("#x:y"))
        self.assertEqual(cfg.max_default_members_per_room, 2)
        self.assertTrue(cfg.allow_federated_invites)
