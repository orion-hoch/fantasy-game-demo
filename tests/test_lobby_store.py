import unittest

import lobby_store


class LobbyStoreSeatMetaTests(unittest.TestCase):
    def setUp(self):
        lobby_store._ROOMS._memory.clear()

    def _create_room_with_players(self, game_type, total_players):
        room = lobby_store.create_room(game_type, "Host", "host-token")
        room_id = room["room_id"]
        for seat_no in range(2, total_players + 1):
            lobby_store.claim_seat(room_id, f"token-{seat_no}", f"P{seat_no}", seat_no)
        return room_id

    def test_team_switch_clears_role_in_codewords_teams(self):
        room_id = self._create_room_with_players("nfl_codewords", 4)

        room = lobby_store.update_seat_meta(room_id, "host-token", {"team": "A"})
        self.assertEqual(room["seats"]["1"]["meta"], {"team": "A"})

        room = lobby_store.update_seat_meta(room_id, "host-token", {"role": "spymaster"})
        self.assertEqual(room["seats"]["1"]["meta"], {"team": "A", "role": "spymaster"})

        room = lobby_store.update_seat_meta(room_id, "host-token", {"team": "B"})
        self.assertEqual(room["seats"]["1"]["meta"], {"team": "B"})

    def test_duplicate_team_role_is_rejected_immediately(self):
        room_id = self._create_room_with_players("nfl_codewords", 4)

        lobby_store.update_seat_meta(room_id, "host-token", {"team": "A", "role": "spymaster"})

        with self.assertRaisesRegex(ValueError, "Red Clue Giver is already taken"):
            lobby_store.update_seat_meta(room_id, "token-2", {"team": "A", "role": "spymaster"})

    def test_duel_team_switch_rejects_taken_team(self):
        room_id = self._create_room_with_players("nfl_codewords_duel", 2)

        lobby_store.update_seat_meta(room_id, "host-token", {"team": "A"})

        with self.assertRaisesRegex(ValueError, "Team Red is already taken"):
            lobby_store.update_seat_meta(room_id, "token-2", {"team": "A"})

        room = lobby_store.update_seat_meta(room_id, "token-2", {"team": "B"})
        self.assertEqual(room["seats"]["2"]["meta"], {"team": "B"})


if __name__ == "__main__":
    unittest.main()
