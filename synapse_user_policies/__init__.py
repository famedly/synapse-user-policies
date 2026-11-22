# Runtime rule: only Synapse and the stdlib may be imported here (pyproject.toml `dependencies = []`).
##= docs/requirements/user-policies.md#fm-pol-20
## At runtime, the module MUST NOT need Python packages other than Synapse and the standard library.
from synapse_user_policies.sso import RandomLocalpartMapping  # noqa: F401
from synapse_user_policies.user_policies import UserPolicies  # noqa: F401
