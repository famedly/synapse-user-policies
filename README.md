# Synapse User Policies

[![PyPI - Version](https://img.shields.io/pypi/v/synapse-user-policies.svg)](https://pypi.org/project/synapse-user-policies)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/synapse-user-policies.svg)](https://pypi.org/project/synapse-user-policies)

A Synapse module that restricts which user types (Synapse `user_type`, `default` if unset) may perform which actions, and enforces room guardrails for everyone: rooms are invite-only, never world-readable, never open to guests, and encrypted from creation.

## Warning: server admins

Synapse skips spam-checker callbacks for server admins. Bots must therefore **never** be server admins, otherwise the action policies do not apply to them. This also applies to the `max_default_members_per_room` cap (enforced in `user_may_invite` and `user_may_send_3pid_invite`), which is skipped for admins. The room guardrails are enforced for admins as well.

## Warning: server notices

Server notices create unencrypted rooms and are therefore incompatible with the guardrails. Do not enable them.

## Installation

The package is not published on PyPI yet; until then install from git:

```console
pip install git+https://github.com/famedly/synapse-user-policies
```

or ship the package directory `synapse_user_policies/` as plain files on Synapse's `PYTHONPATH` (for example mounted from a Kubernetes ConfigMap). The module has no dependencies besides Synapse and the standard library.

## Configuration

```yaml
modules:
  - module: synapse_user_policies.UserPolicies
    config:
      allow:
        # Defaults, shown for reference. Adding `default` to an action re-opens it for users.
        create_room: [bot]
        invite: [bot]
        invite_3pid: []
        send_state_event: [bot]
        join_uninvited_room: [bot]
        create_room_alias: []
        publish_room: []
      always_allowed_state_events: []
      alias_pattern: null
      max_default_members_per_room: 1
      allow_federated_invites: false
```

| Key | Default | Meaning |
| --- | --- | --- |
| `allow` | see the example | Map from action to the list of user types allowed to perform it. Only the actions you name are replaced; the others keep their defaults. An action missing from the effective map is forbidden for everyone. |
| `always_allowed_state_events` | `[]` | State event types that `send_state_event` always permits. |
| `alias_pattern` | `null` | Regular expression that room aliases must match, matched from the start of the alias (`re.match`; applies when `create_room_alias` is allowed); `null` means no restriction. |
| `max_default_members_per_room` | `1` | Maximum number of non-bot users per room (integer >= 1). Every user of any type except `bot` (including `support` and unknown users) who was ever invited or a member counts, also if they left or were banned. Bots are not counted and are never blocked by the cap. Every `m.room.third_party_invite` (invitation by email or phone) counts as one non-bot user, also after it was redeemed. |
| `allow_federated_invites` | `false` | Whether users of other homeservers may invite local users. By default every invitation arriving over federation is rejected. |

User type `default` stands for accounts without `user_type`. Unknown actions, unknown keys or values of the wrong type prevent Synapse from starting. Rejected actions answer with 403 `M_FORBIDDEN`; if the user type cannot be determined the action is rejected.

## Accounts from single sign-on

For homeservers whose users sign in with Synapse's own SSO (`oidc_providers`), the package has an OIDC user mapping provider that gives every new account a random UUIDv4 localpart and takes over nothing else (no display name, avatar or email) from the identity provider, so nobody is asked to pick a username and no localpart can be guessed:

```yaml
oidc_providers:
  - idp_id: google
    # ...
    user_mapping_provider:
      module: synapse_user_policies.RandomLocalpartMapping
```

## Media and external IDs after erasure

When an account is deactivated with `erase` (by a server admin or by the user via `/account/deactivate`), `UserPolicies` deletes all media the account uploaded and removes its external IDs (the link to the identity provider account, so a new sign-in starts a new account); Synapse itself keeps both. The module API has no media calls, so this uses Synapse's store and media repository the way its admin API does.

## Room guardrails

Independent of user type (also for bots): join rule is always `invite`, history visibility is never `world_readable`, guest access is never `can_join` (`private_chat` rooms get `forbidden`), and every room is encrypted from creation. Violating room creations and events are rejected. The encryption algorithm must be `m.megolm.v1.aes-sha2`, both at creation and in later `m.room.encryption` events.

## Warning: workers

The member cap is checked inside one Synapse process (check-then-act). Two invitations handled at the same time by different workers can both pass. In multi-worker deployments, route all membership requests (`/invite`, `/join`, `/state/m.room.member`, `createRoom`) to one worker.

## Warning: federation

Invitations from other homeservers are rejected unless `allow_federated_invites` is `true`. Synapse offers modules no callback for a local user knocking on a room of another homeserver; to prevent that, restrict federation in Synapse itself (for example `federation_domain_whitelist`).

## Testing

```console
# unit tests
uv run --python 3.12 python -m unittest discover -s tests -v

# Complement (needs Docker and Go)
complement/run.sh

# requirement coverage (needs duvet 0.4.3: cargo install duvet --version 0.4.3 --locked)
duvet report        # writes .duvet/snapshot.txt
duvet report --ci   # fails if citations break or coverage differs from the committed snapshot
```

## Requirements

The requirements are specified in [docs/requirements/user-policies.md](docs/requirements/user-policies.md) and traced to code and tests with Duvet.

## License

`synapse-user-policies` is distributed under the terms of the
[AGPL-3.0](https://spdx.org/licenses/AGPL-3.0-only.html) license.
