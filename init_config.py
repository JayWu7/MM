# init_config.py
import importlib.util
import os
import types

def load_config_module_from_file(file_path: str) -> types.ModuleType:
    """
    Dynamically loads a Python module from a given file path.

    Args:
        file_path (str): Path to the Python file containing parameters.

    Returns:
        module: Loaded Python module.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Config file not found: {file_path}")

    module_name = os.path.splitext(os.path.basename(file_path))[0]
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    config_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config_module)
    return config_module

def validate_and_load_config(file_name: str) -> dict:
    """
    Loads and validates configuration parameters from the config py file in ./configs/

    Args:
        file_path (str): Path to the parameter Python file (e.g. runner_paras.py)

    Returns:
        dict: Validated configuration parameters.

    Raises:
        ValueError: If any parameter fails its validation check.
    """
    file_path = f'./configs/{file_name}.py'
    paras = load_config_module_from_file(file_path)
    config = {}

    # === Token & Market Settings ===
    assert isinstance(paras.UNDERLYING_TOKEN, str) and paras.UNDERLYING_TOKEN, "UNDERLYING_TOKEN must be a non-empty string"
    assert isinstance(paras.QUOTE_TOKEN, str) and paras.QUOTE_TOKEN, "QUOTE_TOKEN must be a non-empty string"
    config["underlying_token"] = paras.UNDERLYING_TOKEN.upper()
    config["quote_token"] = paras.QUOTE_TOKEN.upper()
    config["marketplace"] = paras.MARKETPLACE.lower()
    config["hedge_marketplace"] = paras.HEDGE_MARKETPLACE.lower()

    # === Market Making Parameters ===
    assert 0 < paras.MM_PRICE_UP_PCT_LIMIT < 1
    assert 0 < paras.MM_PRICE_DOWN_PCT_LIMIT < 1
    config.update({
        "mm_price_up_pct_limit": paras.MM_PRICE_UP_PCT_LIMIT,
        "mm_price_down_pct_limit": paras.MM_PRICE_DOWN_PCT_LIMIT,
        "mm_bin_step": paras.MM_BIN_STEP,
        "mm_init_inventory_amount": paras.MM_INIT_INVENTORY_AMOUNT,
        "mm_init_quote_amount": paras.MM_INIT_QUOTE_AMOUNT,
        "mm_mode": paras.MM_MODE.lower(),
        "mm_live_order_nums": paras.MM_LIVE_ORDER_NUMS,
        "mm_min_order_size": paras.MM_MIN_ORDER_SIZE,
        "mm_max_order_size": paras.MM_MAX_ORDER_SIZE,
        "mm_iqv_up_limit": paras.MM_IQV_UP_LIMIT,
        "mm_iqv_down_limit": paras.MM_IQV_DOWN_LIMIT,
        "mm_inventory_rb_iqv_ratio": paras.MM_INVENTORY_RB_IQV_RATIO,
        "mm_quote_rb_iqv_ratio": paras.MM_QUOTE_RB_IQV_RATIO,
    })

    # === Auto MM Volatility Controls ===
    config.update({
        "auto_mm_vol_lower_threshold": paras.AUTO_MM_VOL_LOWER_THRESHOLD,
        "auto_mm_vol_upper_threshold": paras.AUTO_MM_VOL_UPPER_THRESHOLD,
    })

    # === Hedge Parameters ===
    config.update({
        "hg_passive_hedge_ratio": paras.HG_PASSIVE_HEDGE_RATIO,
        "hg_min_hedge_order_size": paras.HG_MIN_HEDGE_ORDER_SIZE,
        "hg_active_hedge_iqv_ratio": paras.HG_ACTIVE_HEDGE_IQV_RATIO,
        "hg_passive_hedge_sp_ratio": paras.HG_PASSIVE_HEDGE_SP_RATIO,
        "hg_passive_hedge_proportion": paras.HG_PASSIVE_HEDGE_PROPORTION,
        "hg_passive_hedge_refresh_iqv_ratio": paras.HG_PASSIVE_HEDGE_REFRESH_IQV_RATIO,
        "hg_passive_hedge_refresh_interval": paras.HG_PASSIVE_HEDGE_REFRESH_INTERVAL,
        "hg_dual_sided_hedge": bool(paras.HG_DUAL_SIDED_HEDGE),
    })

    # === Volatility Model Parameters ===
    config.update({
        "vol_his_price_window": paras.VOL_HIS_PRICE_WINDOW,
        "vol_his_price_window_limit": paras.VOL_HIS_PRICE_WINDOW_LIMIT,
        "vol_short_window": paras.VOL_SHORT_WINDOW,
        "vol_long_window": paras.VOL_LONG_WINDOW,
        "vol_ewma_lambda": paras.VOL_EWMA_LAMBDA,
    })

    return config

# Example usage
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python init_config.py path/to/runner_paras.py")
    else:
        cfg = validate_and_load_config(sys.argv[1])
        for k, v in cfg.items():
            print(f"{k}: {v}")
