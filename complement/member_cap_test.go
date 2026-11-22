package complement_test

import (
	"net/http"
	"testing"

	"github.com/matrix-org/complement"
	"github.com/matrix-org/complement/client"
	"github.com/matrix-org/complement/match"
	"github.com/matrix-org/complement/must"
)

func TestMemberCap(t *testing.T) {
	d := complement.Deploy(t, 1)
	defer d.Destroy(t)
	bot := newBot(t, d)

	t.Run("AK-FM-POL-11.1", func(t *testing.T) {
		first, second := newDefaultUser(t, d), newDefaultUser(t, d)
		roomID := botCreateRoom(t, bot, nil)
		bot.MustInviteRoom(t, roomID, first.UserID)
		res := bot.Do(t, "POST", csapi("rooms", roomID, "invite"),
			client.WithJSONBody(t, map[string]any{"user_id": second.UserID}))
		//= docs/requirements/user-policies.md#ak-fm-pol-11-1
		//= type=test
		//# THEN Synapse MUST respond with 403
		mustForbidden(t, res)
		//= docs/requirements/user-policies.md#ak-fm-pol-11-1
		//= type=test
		//# AND the second user MUST NOT receive an invitation
		if n := pendingInvites(t, second); n != 0 {
			t.Fatalf("second user has %d invites", n)
		}
	})

	t.Run("AK-FM-POL-11.2", func(t *testing.T) {
		user, bot2 := newDefaultUser(t, d), newBot(t, d)
		roomID := memberRoom(t, bot, user)
		bot.MustInviteRoom(t, roomID, bot2.UserID)
		//= docs/requirements/user-policies.md#ak-fm-pol-11-2
		//= type=test
		//# THEN the second bot MUST receive the invitation
		if n := pendingInvites(t, bot2); n != 1 {
			t.Fatalf("second bot has %d invites", n)
		}
	})

	t.Run("AK-FM-POL-11.4", func(t *testing.T) {
		user := newDefaultUser(t, d)
		roomID := botCreateRoom(t, bot, nil)
		bot.MustInviteRoom(t, roomID, user.UserID)
		// Without the cap Synapse would go on to the (unreachable) identity server and fail differently.
		res := bot.Do(t, "POST", csapi("rooms", roomID, "invite"),
			client.WithJSONBody(t, map[string]any{
				"id_server": "id.example.org", "id_access_token": "token",
				"medium": "email", "address": "x@example.org",
			}))
		//= docs/requirements/user-policies.md#ak-fm-pol-11-4
		//= type=test
		//# THEN Synapse MUST respond with 403 and M_FORBIDDEN
		must.MatchResponse(t, res, match.HTTPResponse{
			StatusCode: http.StatusForbidden,
			JSON:       []match.JSON{match.JSONKeyEqual("errcode", "M_FORBIDDEN")},
		})
	})

	t.Run("AK-FM-POL-11.3", func(t *testing.T) {
		a, b := newDefaultUser(t, d), newDefaultUser(t, d)
		roomID := botCreateRoom(t, bot, nil)
		bot.MustInviteRoom(t, roomID, a.UserID)
		a.MustJoinRoom(t, roomID, nil)
		a.MustLeaveRoom(t, roomID)
		res := bot.Do(t, "POST", csapi("rooms", roomID, "invite"),
			client.WithJSONBody(t, map[string]any{"user_id": b.UserID}))
		//= docs/requirements/user-policies.md#ak-fm-pol-11-3
		//= type=test
		//# THEN Synapse MUST respond with 403
		mustForbidden(t, res)
		//= docs/requirements/user-policies.md#ak-fm-pol-11-3
		//= type=test
		//# AND the other user MUST NOT receive an invitation
		if n := pendingInvites(t, b); n != 0 {
			t.Fatalf("other user has %d invites", n)
		}
	})
}
