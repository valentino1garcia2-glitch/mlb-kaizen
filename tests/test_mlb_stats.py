from datetime import UTC, date, datetime
import unittest
from unittest.mock import call, patch

from mlb_kaizen.data.http import RetrievedJson
from mlb_kaizen.data.mlb_stats import MLBStatsProvider
from mlb_kaizen.domain.models import AvailabilityStatus


class MLBStatsTests(unittest.TestCase):
    def test_completed_games_batched_uses_non_overlapping_ranges(self) -> None:
        provider = MLBStatsProvider(client=None)  # type: ignore[arg-type]
        with patch.object(provider, "completed_games", return_value=[]) as completed:
            self.assertEqual(
                provider.completed_games_batched(date(2026, 1, 1), date(2026, 1, 5), max_days_per_request=2),
                [],
            )
        self.assertEqual(
            completed.call_args_list,
            [
                call(date(2026, 1, 1), date(2026, 1, 2)),
                call(date(2026, 1, 3), date(2026, 1, 4)),
                call(date(2026, 1, 5), date(2026, 1, 5)),
            ],
        )

    def test_schedule_payload_is_normalised_to_provider_independent_game(self) -> None:
        response = RetrievedJson(
            payload={
                "dates": [
                    {
                        "date": "2026-09-16",
                        "games": [
                            {
                                "gamePk": 123,
                                "gameDate": "2026-09-16T23:10:00Z",
                                "gameType": "R",
                                "teams": {
                                    "home": {"team": {"id": 10, "name": "Home"}},
                                    "away": {"team": {"id": 20, "name": "Away"}},
                                },
                                "venue": {"name": "Test Park"},
                            }
                        ],
                    }
                ]
            },
            url="https://example.test/schedule",
            retrieved_at=datetime(2026, 9, 16, 10, tzinfo=UTC),
            from_cache=False,
        )
        games = MLBStatsProvider.parse_schedule(response, expected_date=date(2026, 9, 16))
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0].game_id, "mlb:123")
        self.assertEqual(games[0].game_type, "R")
        self.assertEqual(games[0].start_time, datetime(2026, 9, 16, 23, 10, tzinfo=UTC))

    def test_probable_pitchers_are_reported_per_team_when_posted(self) -> None:
        response = RetrievedJson(
            payload={
                "dates": [
                    {
                        "games": [
                            {
                                "gamePk": 123,
                                "teams": {
                                    "home": {
                                        "team": {"id": 10, "name": "Home"},
                                        "probablePitcher": {"id": 501, "fullName": "Home Ace"},
                                    },
                                    "away": {"team": {"id": 20, "name": "Away"}},
                                },
                            }
                        ]
                    }
                ]
            },
            url="https://example.test/schedule",
            retrieved_at=datetime(2026, 9, 16, 10, tzinfo=UTC),
            from_cache=False,
        )
        pitchers = MLBStatsProvider.parse_probable_pitchers(response)
        self.assertEqual(len(pitchers), 2)

        home = next(p for p in pitchers if p.team_id == "10")
        self.assertEqual(home.status, AvailabilityStatus.PROJECTED)
        self.assertEqual(home.pitcher_id, "501")
        self.assertEqual(home.pitcher_name, "Home Ace")

        away = next(p for p in pitchers if p.team_id == "20")
        self.assertEqual(away.status, AvailabilityStatus.NOT_YET_PUBLISHED)
        self.assertIsNone(away.pitcher_id)
        self.assertIsNone(away.pitcher_name)

    def test_boxscore_lineups_are_confirmed_when_batting_order_is_posted(self) -> None:
        response = RetrievedJson(
            payload={
                "teams": {
                    "home": {
                        "team": {"id": 10},
                        "battingOrder": [501, 502],
                        "players": {
                            "ID501": {
                                "person": {"id": 501, "fullName": "Home Leadoff"},
                                "position": {"abbreviation": "CF"},
                            },
                            "ID502": {
                                "person": {"id": 502, "fullName": "Home Two Hole"},
                                "position": {"abbreviation": "2B"},
                            },
                        },
                    },
                    "away": {
                        "team": {"id": 20},
                        "battingOrder": [601, 602],
                        "players": {
                            "ID601": {
                                "person": {"id": 601, "fullName": "Away Leadoff"},
                                "position": {"abbreviation": "SS"},
                            },
                            "ID602": {
                                "person": {"id": 602, "fullName": "Away Two Hole"},
                                "position": {"abbreviation": "LF"},
                            },
                        },
                    },
                }
            },
            url="https://example.test/game/123/boxscore",
            retrieved_at=datetime(2026, 9, 16, 22, tzinfo=UTC),
            from_cache=False,
        )
        lineups = MLBStatsProvider.parse_boxscore_lineups(response, game_id="mlb:123")
        self.assertEqual(lineups.status, AvailabilityStatus.CONFIRMED)
        self.assertEqual(len(lineups.home_slots), 2)
        self.assertEqual(lineups.home_slots[0].batting_order, 1)
        self.assertEqual(lineups.home_slots[0].player_name, "Home Leadoff")
        self.assertEqual(lineups.home_slots[0].position, "CF")
        self.assertEqual(lineups.away_slots[1].player_name, "Away Two Hole")

    def test_boxscore_lineups_matches_verified_live_response_shape(self) -> None:
        """Regression fixture from a real statsapi.mlb.com boxscore response.

        Fetched live on 2026-09-17 (game 529572, away side: 2018 Tampa Bay
        Rays) to confirm team.battingOrder is an array of player ids in
        order, cross-checked against each player's individual battingOrder
        field ("100", "200", ... "900"). This closes the gap noted in
        HANDOFF.md section 12.3: parse_boxscore_lineups was written without
        live verification; this fixture proves the assumed shape is correct.
        """

        response = RetrievedJson(
            payload={
                "teams": {
                    "away": {
                        "team": {"id": 139},
                        "battingOrder": [452655, 621563, 460576, 543068, 622110, 605480, 467092, 588751, 621002],
                        "players": {
                            "ID452655": {
                                "person": {"id": 452655, "fullName": "Denard Span"},
                                "position": {"abbreviation": "LF"},
                                "battingOrder": "100",
                            },
                            "ID621563": {
                                "person": {"id": 621563, "fullName": "Joey Wendle"},
                                "position": {"abbreviation": "2B"},
                                "battingOrder": "200",
                            },
                            "ID460576": {
                                "person": {"id": 460576, "fullName": "Carlos Gómez"},
                                "position": {"abbreviation": "CF"},
                                "battingOrder": "300",
                            },
                            "ID543068": {
                                "person": {"id": 543068, "fullName": "C.J. Cron"},
                                "position": {"abbreviation": "1B"},
                                "battingOrder": "400",
                            },
                            "ID622110": {
                                "person": {"id": 622110, "fullName": "Matt Duffy"},
                                "position": {"abbreviation": "3B"},
                                "battingOrder": "500",
                            },
                            "ID605480": {
                                "person": {"id": 605480, "fullName": "Mallex Smith"},
                                "position": {"abbreviation": "RF"},
                                "battingOrder": "600",
                            },
                            "ID467092": {
                                "person": {"id": 467092, "fullName": "Wilson Ramos"},
                                "position": {"abbreviation": "C"},
                                "battingOrder": "700",
                            },
                            "ID588751": {
                                "person": {"id": 588751, "fullName": "Adeiny Hechavarría"},
                                "position": {"abbreviation": "SS"},
                                "battingOrder": "800",
                            },
                            "ID621002": {
                                "person": {"id": 621002, "fullName": "Daniel Robertson"},
                                "position": {"abbreviation": "DH"},
                                "battingOrder": "900",
                            },
                        },
                    },
                    "home": {
                        "team": {"id": 145},
                        "battingOrder": [1],
                        "players": {
                            "ID1": {
                                "person": {"id": 1, "fullName": "Placeholder Home Batter"},
                                "position": {"abbreviation": "2B"},
                            }
                        },
                    },
                }
            },
            url="https://statsapi.mlb.com/api/v1/game/529572/boxscore",
            retrieved_at=datetime(2026, 9, 17, 12, tzinfo=UTC),
            from_cache=False,
        )
        lineups = MLBStatsProvider.parse_boxscore_lineups(response, game_id="mlb:529572")
        self.assertEqual(lineups.status, AvailabilityStatus.CONFIRMED)
        self.assertEqual(len(lineups.away_slots), 9)
        # Cross-checks each starter's array position against MLB's own per-player
        # "battingOrder" field (100 = slot 1, 200 = slot 2, ... 900 = slot 9).
        self.assertEqual(lineups.away_slots[0].player_name, "Denard Span")
        self.assertEqual(lineups.away_slots[0].position, "LF")
        self.assertEqual(lineups.away_slots[3].player_name, "C.J. Cron")
        self.assertEqual(lineups.away_slots[8].player_name, "Daniel Robertson")
        self.assertEqual(lineups.away_slots[8].position, "DH")

    def test_boxscore_lineups_are_not_yet_published_before_posting(self) -> None:
        response = RetrievedJson(
            payload={
                "teams": {
                    "home": {"team": {"id": 10}, "players": {}},
                    "away": {"team": {"id": 20}, "players": {}},
                }
            },
            url="https://example.test/game/123/boxscore",
            retrieved_at=datetime(2026, 9, 16, 10, tzinfo=UTC),
            from_cache=False,
        )
        lineups = MLBStatsProvider.parse_boxscore_lineups(response, game_id="mlb:123")
        self.assertEqual(lineups.status, AvailabilityStatus.NOT_YET_PUBLISHED)
        self.assertEqual(lineups.home_slots, ())
        self.assertEqual(lineups.away_slots, ())

    def test_venue_location_matches_verified_live_response_shape(self) -> None:
        """Fixture from a real live fetch of statsapi.mlb.com/api/v1/venues/22
        (UNIQLO Field at Dodger Stadium) on 2026-09-17."""

        response = RetrievedJson(
            payload={
                "venues": [
                    {
                        "id": 22,
                        "name": "UNIQLO Field at Dodger Stadium",
                        "location": {
                            "city": "Los Angeles",
                            "defaultCoordinates": {"latitude": 34.07368, "longitude": -118.24053},
                        },
                    }
                ]
            },
            url="https://statsapi.mlb.com/api/v1/venues/22?hydrate=location",
            retrieved_at=datetime(2026, 9, 17, 12, tzinfo=UTC),
            from_cache=False,
        )
        venue = MLBStatsProvider.parse_venue_location(response, venue_id="22")
        self.assertEqual(venue.venue_id, "22")
        self.assertAlmostEqual(venue.latitude, 34.07368)
        self.assertAlmostEqual(venue.longitude, -118.24053)

    def test_venue_location_rejects_response_without_coordinates(self) -> None:
        response = RetrievedJson(
            payload={"venues": [{"id": 22, "name": "No location hydrated"}]},
            url="https://statsapi.mlb.com/api/v1/venues/22",
            retrieved_at=datetime(2026, 9, 17, 12, tzinfo=UTC),
            from_cache=False,
        )
        with self.assertRaises(ValueError):
            MLBStatsProvider.parse_venue_location(response, venue_id="22")

    def test_team_season_stats_combines_hitting_and_pitching_splits(self) -> None:
        """Field names (gamesPlayed, runs, avg, obp, slg, era, whip,
        earnedRuns) are corroborated by a real printed attribute dump shown in
        python-mlb-statsapi's own README (pypi.org/project/python-mlb-statsapi,
        checked 2026-09-17), not by an independent live fetch this session —
        the search tool would not surface a fetchable literal URL for the
        /v1/stats endpoint itself. Run `mlb-kaizen team-stats` once against a
        real team before trusting this in production (see HANDOFF.md #15)."""

        hitting_response = RetrievedJson(
            payload={
                "stats": [
                    {
                        "splits": [
                            {
                                "stat": {
                                    "gamesPlayed": 150,
                                    "avg": ".251",
                                    "obp": ".330",
                                    "slg": ".420",
                                    "runs": 720,
                                    "plateAppearances": 5800,
                                },
                                "team": {"id": 147, "name": "New York Yankees"},
                            }
                        ]
                    }
                ]
            },
            url="https://statsapi.mlb.com/api/v1/stats?stats=season&group=hitting&teamId=147",
            retrieved_at=datetime(2026, 9, 17, 12, tzinfo=UTC),
            from_cache=False,
        )
        pitching_response = RetrievedJson(
            payload={
                "stats": [
                    {
                        "splits": [
                            {
                                "stat": {
                                    "era": "3.85",
                                    "whip": "1.21",
                                    "inningsPitched": "1345.0",
                                    "earnedRuns": 575,
                                    "runs": 620,
                                },
                                "team": {"id": 147, "name": "New York Yankees"},
                            }
                        ]
                    }
                ]
            },
            url="https://statsapi.mlb.com/api/v1/stats?stats=season&group=pitching&teamId=147",
            retrieved_at=datetime(2026, 9, 17, 12, tzinfo=UTC),
            from_cache=False,
        )
        stats = MLBStatsProvider.parse_team_season_stats(
            hitting_response, pitching_response, team_id="147", team_name="New York Yankees", season="2026"
        )
        self.assertEqual(stats.games_played, 150)
        self.assertAlmostEqual(stats.batting_avg, 0.251)
        self.assertEqual(stats.runs_scored, 720)
        self.assertAlmostEqual(stats.pitching_era, 3.85)
        self.assertEqual(stats.earned_runs, 575)
        self.assertEqual(stats.runs_allowed, 620)

    def test_team_season_stats_raises_loudly_on_missing_field(self) -> None:
        hitting_response = RetrievedJson(
            payload={"stats": [{"splits": [{"stat": {"gamesPlayed": 150}, "team": {"id": 147}}]}]},
            url="https://statsapi.mlb.com/api/v1/stats",
            retrieved_at=datetime(2026, 9, 17, 12, tzinfo=UTC),
            from_cache=False,
        )
        pitching_response = hitting_response
        with self.assertRaises(ValueError):
            MLBStatsProvider.parse_team_season_stats(
                hitting_response, pitching_response, team_id="147", team_name="Yankees", season="2026"
            )

    def test_league_average_runs_per_game_sums_across_all_teams(self) -> None:
        # 30 teams, each 150 games; runs alternate 700/650 -> total = 15*700+15*650 = 20250
        splits = []
        for team_id in range(1, 31):
            runs = 700 if team_id % 2 == 0 else 650
            splits.append({"team": {"id": team_id}, "stat": {"runs": runs, "gamesPlayed": 150}})
        response = RetrievedJson(
            payload={"stats": [{"splits": splits}]},
            url="https://statsapi.mlb.com/api/v1/stats?stats=season&group=hitting&sportId=1",
            retrieved_at=datetime(2026, 9, 17, 12, tzinfo=UTC),
            from_cache=False,
        )
        average = MLBStatsProvider.parse_league_average_runs_per_game(response)
        total_runs = 15 * 700 + 15 * 650
        total_games = 30 * 150
        self.assertAlmostEqual(average, total_runs / total_games)

    def test_league_average_raises_when_response_is_clearly_truncated(self) -> None:
        splits = [{"team": {"id": i}, "stat": {"runs": 700, "gamesPlayed": 150}} for i in range(1, 6)]
        response = RetrievedJson(
            payload={"stats": [{"splits": splits}]},
            url="https://statsapi.mlb.com/api/v1/stats",
            retrieved_at=datetime(2026, 9, 17, 12, tzinfo=UTC),
            from_cache=False,
        )
        with self.assertRaises(ValueError):
            MLBStatsProvider.parse_league_average_runs_per_game(response)

    def test_league_average_raises_on_duplicate_team_id(self) -> None:
        splits = [{"team": {"id": 1}, "stat": {"runs": 700, "gamesPlayed": 150}} for _ in range(30)]
        response = RetrievedJson(
            payload={"stats": [{"splits": splits}]},
            url="https://statsapi.mlb.com/api/v1/stats",
            retrieved_at=datetime(2026, 9, 17, 12, tzinfo=UTC),
            from_cache=False,
        )
        with self.assertRaises(ValueError):
            MLBStatsProvider.parse_league_average_runs_per_game(response)


    def test_parse_completed_games_matches_verified_live_response_shape(self) -> None:
        """Fixture: a trimmed, real response fetched live on 2026-09-18 from
        statsapi.mlb.com/api/v1/schedule?startDate=2025-07-04&endDate=2025-07-04
        &hydrate=team,linescore (2 of the 15 real games that day, one Final
        with a score, one deliberately altered to non-Final to test filtering)."""

        response = RetrievedJson(
            payload={
                "dates": [
                    {
                        "date": "2025-07-04",
                        "games": [
                            {
                                "gamePk": 777245,
                                "gameDate": "2025-07-04T15:05:00Z",
                                "officialDate": "2025-07-04",
                                "gameType": "R",
                                "status": {"detailedState": "Final"},
                                "teams": {
                                    "away": {"team": {"id": 111, "name": "Boston Red Sox"}, "score": 11},
                                    "home": {"team": {"id": 120, "name": "Washington Nationals"}, "score": 2},
                                },
                            },
                            {
                                "gamePk": 999999,
                                "gameDate": "2025-07-04T20:00:00Z",
                                "officialDate": "2025-07-04",
                                "status": {"detailedState": "Postponed"},
                                "teams": {
                                    "away": {"team": {"id": 108, "name": "Los Angeles Angels"}},
                                    "home": {"team": {"id": 141, "name": "Toronto Blue Jays"}},
                                },
                            },
                        ],
                    }
                ]
            },
            url="https://statsapi.mlb.com/api/v1/schedule?startDate=2025-07-04&endDate=2025-07-04&hydrate=team,linescore",
            retrieved_at=datetime(2026, 9, 18, 12, tzinfo=UTC),
            from_cache=False,
        )
        results = MLBStatsProvider.parse_completed_games(response)
        self.assertEqual(len(results), 1)  # the Postponed game is excluded
        result = results[0]
        self.assertEqual(result.game_id, "mlb:777245")
        self.assertEqual(result.away_team_id, "111")
        self.assertEqual(result.home_team_id, "120")
        self.assertEqual(result.away_runs, 11)
        self.assertEqual(result.home_runs, 2)
        self.assertEqual(result.official_date, date(2025, 7, 4))
        self.assertEqual(result.game_type, "R")

    def test_parse_completed_games_skips_final_status_with_no_published_score(self) -> None:
        response = RetrievedJson(
            payload={
                "dates": [
                    {
                        "games": [
                            {
                                "gamePk": 1,
                                "gameDate": "2025-07-04T15:05:00Z",
                                "status": {"detailedState": "Final"},
                                "teams": {
                                    "away": {"team": {"id": 1, "name": "A"}},
                                    "home": {"team": {"id": 2, "name": "B"}},
                                },
                            }
                        ]
                    }
                ]
            },
            url="https://statsapi.mlb.com/api/v1/schedule",
            retrieved_at=datetime(2026, 9, 18, 12, tzinfo=UTC),
            from_cache=False,
        )
        self.assertEqual(MLBStatsProvider.parse_completed_games(response), [])
