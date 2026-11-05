package complement_test

import (
	"testing"

	"github.com/matrix-org/complement"
	"github.com/matrix-org/complement/client"
)

func TestFederatedInvite(t *testing.T) {
	d := complement.Deploy(t, 2)
	defer d.Destroy(t)
	user := newDefaultUser(t, d)
	remoteBot := newBotOn(t, d, "hs2")
	roomID := botCreateRoom(t, remoteBot, nil)

	res := remoteBot.Do(t, "POST", csapi("rooms", roomID, "invite"),
		client.WithJSONBody(t, map[string]any{"user_id": user.UserID}))
	//= docs/requirements/user-policies.md#ak-fm-pol-7-1
	//= type=test
	//# THEN the invitation MUST fail
	if res.StatusCode < 400 {
		t.Fatalf("federated invite accepted with %d", res.StatusCode)
	}
	//= docs/requirements/user-policies.md#ak-fm-pol-7-1
	//= type=test
	//# AND the invited user MUST NOT receive an invitation
	if n := pendingInvites(t, user); n != 0 {
		t.Fatalf("user has %d invites", n)
	}
}
