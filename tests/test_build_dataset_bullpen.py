from datetime import UTC, datetime
import unittest
from .conftest import completed_game, starter_line
from mlb_kaizen.domain.models import PitcherGameLine
from mlb_kaizen.training.build_dataset import build_point_in_time_rows_with_bullpen

class BuildPointInTimeRowsWithBullpenTests(unittest.TestCase):
    def _inputs(self, count=5):
        games=[]; lines=[]
        for i in range(1,count+1):
            game=completed_game(game_id=f'mlb:{i}',start_time=datetime(2025,7,i,tzinfo=UTC),home_runs=4,away_runs=3); games.append(game)
            for side,pid in (('home',f'H{i}'),('away',f'A{i}')):
                base=starter_line(game_id=game.game_id,pitcher_id=pid,side=side,earned_runs=1,innings_pitched='1.0')
                lines.append(PitcherGameLine(base.game_id,base.pitcher_id,base.pitcher_name,base.side,base.innings_pitched,base.runs_allowed,base.earned_runs,False,base.provenance))
        return games,lines
    def _rows(self):
        games,lines=self._inputs(); return build_point_in_time_rows_with_bullpen(games,lines,minimum_prior_games=1,minimum_league_games_for_average=2,minimum_team_bullpen_outs=1,minimum_league_outs_for_average=1)
    def test_row_includes_bullpen_era_index_once_thresholds_are_met(self): self.assertIn('home_bullpen_era_index',self._rows()[0].features)
    def test_games_below_bullpen_threshold_are_skipped(self):
        games,lines=self._inputs(); self.assertFalse(build_point_in_time_rows_with_bullpen(games,lines,minimum_team_bullpen_outs=999))
    def test_a_games_own_relief_runs_never_appear_in_its_own_bullpen_index(self):
        games, lines = self._inputs(4)
        # The home reliever's 20 ER in game 3 must appear only from game 4.
        lines[4] = PitcherGameLine(lines[4].game_id, lines[4].pitcher_id, lines[4].pitcher_name, lines[4].side, '1.0', 20, 20, False, lines[4].provenance)
        rows = build_point_in_time_rows_with_bullpen(games, lines, minimum_prior_games=1, minimum_league_games_for_average=2, minimum_team_bullpen_outs=1, minimum_league_outs_for_average=1)
        by = {row.game_id: row for row in rows}
        self.assertLess(by['mlb:3'].features['home_bullpen_era_index'], by['mlb:4'].features['home_bullpen_era_index'])
    def test_bullpen_lines_for_a_game_not_in_the_games_list_are_ignored(self):
        games,lines=self._inputs(); extra=lines[0]; lines.append(PitcherGameLine('mlb:missing',extra.pitcher_id,extra.pitcher_name,'home','1.0',0,0,False,extra.provenance)); self.assertTrue(build_point_in_time_rows_with_bullpen(games,lines,minimum_prior_games=1,minimum_league_games_for_average=2,minimum_team_bullpen_outs=1,minimum_league_outs_for_average=1))
    def test_feature_timestamp_never_exceeds_prediction_timestamp(self):
        for row in self._rows(): self.assertLessEqual(row.feature_timestamp,row.prediction_timestamp)
    def test_rejects_non_positive_thresholds(self):
        games,lines=self._inputs()
        with self.assertRaises(ValueError): build_point_in_time_rows_with_bullpen(games,lines,minimum_team_bullpen_outs=0)
