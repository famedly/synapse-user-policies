import unittest


class SmokeTest(unittest.TestCase):
    def test_import(self):
        from synapse_user_policies import UserPolicies

        self.assertTrue(callable(UserPolicies.parse_config))
