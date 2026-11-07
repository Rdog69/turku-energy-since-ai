import unittest
from unittest.mock import patch, MagicMock
import numpy as np
import pandas as pd
from src.models.gbm import GBMModel


class TestGBMCalProductNoRecency(unittest.TestCase):
    @patch('src.models.gbm.lgb.LGBMRegressor')
    @patch('src.models.gbm.lgb.LGBMClassifier')
    def test_min_child_samples_effect(self, mock_classifier, mock_regressor):
        """Test that min_child_samples parameter is correctly passed to LightGBM models."""
        # Setup mock returns
        mock_regressor_instance = MagicMock()
        mock_classifier_instance = MagicMock()
        mock_regressor.return_value = mock_regressor_instance
        mock_classifier.return_value = mock_classifier_instance
        
        # Create a minimal training dataframe
        train_df = pd.DataFrame({
            'y_gap': [1, 2, 3],
            'y_dir': [1, -1, 0],
            'y_spike_high': [0, 1, 0],
            'y_spike_low': [1, 0, 0],
            'y_first_usable': pd.to_datetime(['2026-06-01', '2026-06-02', '2026-06-03']),
            'origin': pd.to_datetime(['2026-06-01', '2026-06-02', '2026-06-03']),
            'delivery': pd.to_datetime(['2026-07-01', '2026-07-02', '2026-07-03']),
            'step': [1, 2, 3],
            'spot': [20.0, 21.0, 22.0]
        })
        
        # Add feature columns from FEATURE_COLUMNS list
        for i, col in enumerate([
            "spot_ramp_in", "spot_ramp_out", "spot_abs_ramp", "spot_minus_horizon_mean",
            "wind_fc", "wind_fc_ramp_1h", "wind_share", "cons_fc", "solar_fc", "residual_load_fc",
            "cap_fi_ee", "cap_ee_fi", "hour", "weekday", "holiday", "dst", "quarter",
            "last_gap", "mean_gap_last4", "mean_gap_last8", "last_dir", "mean_dir_last4", "mean_dir_last8",
            "last_mfrr_up_mw", "last_mfrr_down_mw", "last_cons_err",
            "last_flow_se1", "last_flow_se3", "last_flow_no4", "last_flow_ee",
            "last_se1_imb_gap", "last_se3_imb_gap", "last_ee_imb_gap", "age_q"
        ]):
            train_df[col] = [0.1 * i] * 3
            
        # Initialize model with our change
        model = GBMModel()
        model.fit(train_df, pd.Timestamp('2026-06-03'))
        
        # Check that min_child_samples=500 was passed to regressor constructors
        regressor_calls = mock_regressor.call_args_list
        for call in regressor_calls:
            self.assertEqual(call[1]['min_child_samples'], 500)
            
        # Check that min_child_samples=500 was passed to classifier constructors
        classifier_calls = mock_classifier.call_args_list
        for call in classifier_calls:
            self.assertEqual(call[1]['min_child_samples'], 500)


if __name__ == '__main__':
    unittest.main()