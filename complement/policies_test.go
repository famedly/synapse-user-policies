package complement_test

import (
	"net/http"
	"testing"

	"github.com/matrix-org/complement"
	"github.com/matrix-org/complement/client"
	"github.com/matrix-org/complement/match"
	"github.com/matrix-org/complement/must"
)

func TestDefaultCannotCreateRoom(t *testing.T) {
	//= docs/requirements/user-policies.md#ak-fm-pol-2-1
	//= type=test
	//# THEN Synapse MUST respond with 403 and M_FORBIDDEN
	d := complement.Deploy(t, 1)
	defer d.Destroy(t)
	user := newDefaultUser(t, d)

	res := user.Do(t, "POST", []string{"_matrix", "client", "v3", "createRoom"},
		client.WithJSONBody(t, botCreateRoomBody(nil)))
	must.MatchResponse(t, res, match.HTTPResponse{
		StatusCode: http.StatusForbidden,
		JSON:       []match.JSON{match.JSONKeyEqual("errcode", "M_FORBIDDEN")},
	})

	//= docs/requirements/user-policies.md#ak-fm-pol-2-1
	//= type=test
	//# AND no room MUST be created
	res = user.MustDo(t, "GET", []string{"_matrix", "client", "v3", "joined_rooms"})
	must.MatchResponse(t, res, match.HTTPResponse{
		JSON: []match.JSON{match.JSONKeyArrayOfSize("joined_rooms", 0)},
	})
}

func TestBotCanCreateRoom(t *testing.T) {
	//= docs/requirements/user-policies.md#ak-fm-pol-2-2
	//= type=test
	//# THEN the room MUST be created
	d := complement.Deploy(t, 1)
	defer d.Destroy(t)
	bot := newBot(t, d)

	if roomID := botCreateRoom(t, bot, nil); roomID == "" {
		t.Fatal("createRoom returned no room_id")
	}
}
