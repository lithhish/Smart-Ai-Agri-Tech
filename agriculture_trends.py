"""
agriculture_trends.py - Multi-Year Agro-Climatic, Crop Growth, Mandi Pricing & Farmer Economic Yield Intelligence.
Provides month-by-month and seasonal trends for 2024, 2025, and 2026:
- Weather & Meteorological Rainfall (mm) & Temperature (°C)
- Plant & Crop Vegetative Growth Progression (NDVI / Growth Index %)
- Agmarknet & e-NAM Mandi Market Prices (₹/quintal)
- Farmer Yield Increase (Traditional vs IoT Precision Smart Farming, quintals/acre)
- Farmer Net Benefit & Economic Gain (₹/acre profit increase from water, power & yield boost)
"""

from typing import Dict, Any, List

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

ANNUAL_DATA: Dict[int, Dict[str, Any]] = {
    2024: {
        "year": 2024,
        "climate_description": "El Niño Climate Pattern (+1.8°C ENSO anomaly) - Moderate Southwest monsoon with intense late Northeast monsoon rainfall.",
        "annual_rainfall_mm": 812.4,
        "avg_temperature_c": 28.6,
        "weather": {
            "rainfall_mm": [9.5, 4.2, 11.0, 29.5, 58.4, 76.2, 88.0, 95.5, 112.0, 168.4, 134.2, 25.5],
            "temp_c": [25.1, 27.4, 30.2, 33.1, 33.8, 31.2, 29.5, 29.0, 29.2, 27.8, 26.0, 24.8],
            "humidity_pct": [60, 56, 52, 58, 65, 72, 77, 79, 81, 86, 80, 68]
        },
        "crops": {
            "Sugarcane": {
                "growth_stage": ["Germination", "Tillering", "Tillering", "Grand Growth", "Grand Growth", "Elongation", "Elongation", "Canopy Close", "Ripening", "Ripening", "Maturity", "Harvest"],
                "growth_index_pct": [12, 24, 38, 54, 68, 80, 88, 93, 96, 98, 99, 92],
                "market_price_inr_qtl": [305, 308, 310, 312, 315, 318, 320, 322, 325, 328, 330, 332],
                "traditional_yield_qtl_acre": 298.0,
                "smart_iot_yield_qtl_acre": 395.0,
                "yield_gain_pct": 32.5,
                "yield_progression_pct": [10, 20, 32, 48, 62, 75, 85, 92, 96, 99, 100, 100],
                "farmer_net_benefit_inr_acre": [1100, 2300, 4800, 8200, 13100, 19500, 26400, 32800, 38600, 44100, 49500, 54800]
            },
            "Cotton": {
                "growth_stage": ["Field Prep", "Sowing", "Germination", "Squaring", "Flowering", "Boll Formation", "Boll Bursting", "Harvest 1", "Harvest 2", "Harvest 3", "Rabi Prep", "Soil Resting"],
                "growth_index_pct": [5, 16, 30, 50, 70, 84, 94, 98, 88, 75, 18, 8],
                "market_price_inr_qtl": [6520, 6580, 6640, 6750, 6820, 6900, 7050, 7120, 7180, 7240, 7300, 7260],
                "traditional_yield_qtl_acre": 10.8,
                "smart_iot_yield_qtl_acre": 14.5,
                "yield_gain_pct": 34.2,
                "yield_progression_pct": [5, 12, 24, 42, 65, 82, 92, 98, 92, 80, 0, 0],
                "farmer_net_benefit_inr_acre": [750, 1650, 3900, 7200, 12400, 19100, 27200, 35400, 41100, 46200, 47800, 47800]
            },
            "Groundnut": {
                "growth_stage": ["Sowing", "Vegetative", "Flowering", "Pegging", "Pod Formation", "Maturity", "Harvest", "Post-Harvest", "Rabi Sowing", "Vegetative", "Flowering", "Pegging"],
                "growth_index_pct": [14, 35, 62, 84, 95, 98, 90, 15, 28, 45, 66, 82],
                "market_price_inr_qtl": [6250, 6290, 6340, 6400, 6450, 6520, 6560, 6600, 6640, 6680, 6720, 6750],
                "traditional_yield_qtl_acre": 15.6,
                "smart_iot_yield_qtl_acre": 21.0,
                "yield_gain_pct": 34.6,
                "yield_progression_pct": [10, 28, 52, 76, 92, 98, 88, 15, 30, 50, 72, 88],
                "farmer_net_benefit_inr_acre": [850, 1900, 4400, 8400, 14900, 22400, 30100, 31500, 33800, 36900, 41200, 44800]
            },
            "Paddy / Rice": {
                "growth_stage": ["Nursery", "Transplanting", "Tillering", "Panicle Initiation", "Booting", "Heading", "Milking", "Dough Stage", "Harvest (Kuruvai)", "Samba Sowing", "Transplanting", "Tillering"],
                "growth_index_pct": [10, 25, 48, 70, 84, 94, 97, 98, 88, 22, 38, 58],
                "market_price_inr_qtl": [2120, 2135, 2150, 2165, 2178, 2190, 2205, 2218, 2230, 2245, 2255, 2270],
                "traditional_yield_qtl_acre": 23.2,
                "smart_iot_yield_qtl_acre": 31.4,
                "yield_gain_pct": 35.3,
                "yield_progression_pct": [8, 22, 45, 66, 82, 92, 96, 98, 88, 20, 38, 62],
                "farmer_net_benefit_inr_acre": [950, 2150, 4700, 8900, 14400, 21000, 28100, 34800, 38100, 40400, 43800, 48200]
            }
        }
    },
    2025: {
        "year": 2025,
        "climate_description": "Optimal ENSO-Neutral / La Niña Transition - Excellent pre-monsoon showers and balanced Southwest/Northeast monsoon rainfall distribution.",
        "annual_rainfall_mm": 961.0,
        "avg_temperature_c": 27.9,
        "weather": {
            "rainfall_mm": [12.4, 8.1, 15.6, 38.2, 74.5, 92.1, 110.8, 125.4, 142.0, 195.6, 118.2, 28.5],
            "temp_c": [24.5, 26.8, 29.5, 32.1, 33.0, 30.5, 28.9, 28.2, 28.5, 27.2, 25.4, 24.1],
            "humidity_pct": [62, 58, 55, 60, 68, 76, 80, 82, 85, 88, 82, 70]
        },
        "crops": {
            "Sugarcane": {
                "growth_stage": ["Germination", "Tillering", "Tillering", "Grand Growth", "Grand Growth", "Elongation", "Elongation", "Canopy Close", "Ripening", "Ripening", "Maturity", "Harvest"],
                "growth_index_pct": [15, 28, 42, 58, 72, 84, 91, 95, 98, 100, 100, 95],
                "market_price_inr_qtl": [315, 318, 322, 325, 328, 330, 332, 335, 338, 340, 342, 345],
                "traditional_yield_qtl_acre": 325.0,
                "smart_iot_yield_qtl_acre": 428.0,
                "yield_gain_pct": 31.7,
                "yield_progression_pct": [10, 22, 35, 50, 65, 78, 88, 94, 97, 100, 100, 100],
                "farmer_net_benefit_inr_acre": [1200, 2500, 5100, 8900, 14200, 21000, 28500, 35000, 41200, 46800, 52400, 58600]
            },
            "Cotton": {
                "growth_stage": ["Field Prep", "Sowing", "Germination", "Squaring", "Flowering", "Boll Formation", "Boll Bursting", "Harvest 1", "Harvest 2", "Harvest 3", "Rabi Prep", "Soil Resting"],
                "growth_index_pct": [5, 18, 32, 54, 75, 89, 96, 100, 92, 80, 20, 10],
                "market_price_inr_qtl": [6750, 6820, 6900, 7050, 7120, 7200, 7350, 7420, 7480, 7550, 7620, 7580],
                "traditional_yield_qtl_acre": 11.5,
                "smart_iot_yield_qtl_acre": 15.6,
                "yield_gain_pct": 35.6,
                "yield_progression_pct": [5, 12, 25, 45, 68, 85, 95, 100, 95, 85, 0, 0],
                "farmer_net_benefit_inr_acre": [800, 1800, 4200, 7900, 13500, 20800, 29400, 38500, 44200, 49800, 51200, 51200]
            },
            "Groundnut": {
                "growth_stage": ["Sowing", "Vegetative", "Flowering", "Pegging", "Pod Formation", "Maturity", "Harvest", "Post-Harvest", "Rabi Sowing", "Vegetative", "Flowering", "Pegging"],
                "growth_index_pct": [15, 38, 65, 88, 97, 100, 94, 15, 25, 42, 68, 85],
                "market_price_inr_qtl": [6380, 6420, 6490, 6550, 6610, 6680, 6720, 6750, 6790, 6820, 6860, 6900],
                "traditional_yield_qtl_acre": 16.5,
                "smart_iot_yield_qtl_acre": 22.4,
                "yield_gain_pct": 35.8,
                "yield_progression_pct": [10, 30, 55, 80, 95, 100, 90, 15, 30, 50, 75, 90],
                "farmer_net_benefit_inr_acre": [950, 2100, 4800, 9200, 16400, 24500, 32800, 34200, 36500, 39800, 44500, 48200]
            },
            "Paddy / Rice": {
                "growth_stage": ["Nursery", "Transplanting", "Tillering", "Panicle Initiation", "Booting", "Heading", "Milking", "Dough Stage", "Harvest (Kuruvai)", "Samba Sowing", "Transplanting", "Tillering"],
                "growth_index_pct": [12, 28, 52, 74, 88, 96, 99, 100, 92, 20, 35, 60],
                "market_price_inr_qtl": [2183, 2195, 2210, 2225, 2240, 2250, 2265, 2280, 2295, 2310, 2320, 2335],
                "traditional_yield_qtl_acre": 24.5,
                "smart_iot_yield_qtl_acre": 33.2,
                "yield_gain_pct": 35.5,
                "yield_progression_pct": [10, 25, 48, 70, 85, 95, 98, 100, 90, 20, 40, 65],
                "farmer_net_benefit_inr_acre": [1100, 2400, 5200, 9800, 15800, 22900, 30500, 37800, 41200, 43500, 47100, 51800]
            }
        }
    },
    2026: {
        "year": 2026,
        "climate_description": "Current Operational Year (El Niño Phase Observed: +2.2°C) - Warm summer with heavy monsoon surge and high relative humidity (>85%).",
        "annual_rainfall_mm": 938.5,
        "avg_temperature_c": 28.3,
        "weather": {
            "rainfall_mm": [14.0, 6.5, 18.2, 42.0, 68.0, 88.5, 104.2, 120.0, 138.5, 188.0, 122.5, 28.1],
            "temp_c": [24.8, 27.0, 29.8, 32.5, 33.2, 30.8, 29.1, 28.5, 28.7, 27.5, 25.8, 24.3],
            "humidity_pct": [64, 60, 57, 63, 70, 78, 82, 85, 87, 90, 84, 72]
        },
        "crops": {
            "Sugarcane": {
                "growth_stage": ["Germination", "Tillering", "Tillering", "Grand Growth", "Grand Growth", "Elongation", "Elongation", "Canopy Close", "Ripening", "Ripening", "Maturity", "Harvest"],
                "growth_index_pct": [16, 30, 44, 60, 74, 85, 92, 96, 99, 100, 100, 96],
                "market_price_inr_qtl": [325, 328, 332, 335, 338, 340, 342, 345, 348, 350, 352, 355],
                "traditional_yield_qtl_acre": 330.0,
                "smart_iot_yield_qtl_acre": 435.0,
                "yield_gain_pct": 31.8,
                "yield_progression_pct": [12, 24, 38, 52, 68, 80, 90, 95, 98, 100, 100, 100],
                "farmer_net_benefit_inr_acre": [1300, 2700, 5400, 9400, 15000, 22200, 30100, 37000, 43500, 49500, 55400, 61800]
            },
            "Cotton": {
                "growth_stage": ["Field Prep", "Sowing", "Germination", "Squaring", "Flowering", "Boll Formation", "Boll Bursting", "Harvest 1", "Harvest 2", "Harvest 3", "Rabi Prep", "Soil Resting"],
                "growth_index_pct": [6, 20, 35, 56, 78, 91, 98, 100, 94, 82, 22, 12],
                "market_price_inr_qtl": [6950, 7020, 7100, 7220, 7300, 7380, 7500, 7580, 7650, 7720, 7780, 7740],
                "traditional_yield_qtl_acre": 11.8,
                "smart_iot_yield_qtl_acre": 16.2,
                "yield_gain_pct": 37.3,
                "yield_progression_pct": [6, 14, 28, 48, 72, 88, 96, 100, 96, 86, 0, 0],
                "farmer_net_benefit_inr_acre": [900, 2000, 4600, 8600, 14800, 22600, 31800, 41200, 47500, 53400, 54800, 54800]
            },
            "Groundnut": {
                "growth_stage": ["Sowing", "Vegetative", "Flowering", "Pegging", "Pod Formation", "Maturity", "Harvest", "Post-Harvest", "Rabi Sowing", "Vegetative", "Flowering", "Pegging"],
                "growth_index_pct": [16, 40, 68, 90, 98, 100, 95, 18, 28, 45, 70, 88],
                "market_price_inr_qtl": [6550, 6600, 6680, 6740, 6800, 6870, 6920, 6960, 7000, 7050, 7100, 7150],
                "traditional_yield_qtl_acre": 17.0,
                "smart_iot_yield_qtl_acre": 23.2,
                "yield_gain_pct": 36.5,
                "yield_progression_pct": [12, 32, 58, 82, 96, 100, 92, 18, 32, 52, 78, 92],
                "farmer_net_benefit_inr_acre": [1050, 2300, 5200, 9900, 17500, 26000, 34800, 36200, 38800, 42400, 47200, 51400]
            },
            "Paddy / Rice": {
                "growth_stage": ["Nursery", "Transplanting", "Tillering", "Panicle Initiation", "Booting", "Heading", "Milking", "Dough Stage", "Harvest (Kuruvai)", "Samba Sowing", "Transplanting", "Tillering"],
                "growth_index_pct": [14, 30, 55, 76, 90, 98, 100, 100, 94, 24, 38, 64],
                "market_price_inr_qtl": [2250, 2265, 2280, 2295, 2310, 2325, 2340, 2355, 2370, 2385, 2400, 2415],
                "traditional_yield_qtl_acre": 25.0,
                "smart_iot_yield_qtl_acre": 34.0,
                "yield_gain_pct": 36.0,
                "yield_progression_pct": [12, 28, 52, 74, 88, 96, 99, 100, 92, 24, 42, 68],
                "farmer_net_benefit_inr_acre": [1200, 2600, 5600, 10500, 16900, 24400, 32500, 40200, 43800, 46200, 50100, 55200]
            }
        }
    }
}


def get_annual_analytics_data(year: int = 2025, crop: str = "Sugarcane") -> Dict[str, Any]:
    """Return full annual analytics for the selected year and crop."""
    target_year = year if year in ANNUAL_DATA else 2025
    year_obj = ANNUAL_DATA[target_year]

    crops_data = year_obj["crops"]
    selected_crop_key = crop if crop in crops_data else "Sugarcane"
    crop_info = crops_data[selected_crop_key]

    return {
        "success": True,
        "selected_year": target_year,
        "available_years": [2024, 2025, 2026],
        "available_crops": list(crops_data.keys()),
        "selected_crop": selected_crop_key,
        "climate_description": year_obj["climate_description"],
        "annual_rainfall_mm": year_obj["annual_rainfall_mm"],
        "avg_temperature_c": year_obj["avg_temperature_c"],
        "months": MONTHS,
        "weather": year_obj["weather"],
        "crop_data": crop_info,
        "all_crops": {k: {
            "traditional_yield_qtl_acre": v["traditional_yield_qtl_acre"],
            "smart_iot_yield_qtl_acre": v["smart_iot_yield_qtl_acre"],
            "yield_gain_pct": v["yield_gain_pct"],
            "max_benefit_inr": v["farmer_net_benefit_inr_acre"][-1]
        } for k, v in crops_data.items()}
    }
