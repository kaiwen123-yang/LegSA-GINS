import math

from legsa_gins.paper_rebuild.clean2_ablation import effect_coefficient, reported_factorial_effect


def test_factorial_beta_and_doubled_effect_formula(ablation_catalog):
    values = {}
    for variant in ablation_catalog.variants:
        values[variant.ablation_id] = 5.0 + 2.0 * variant.effect_code("RD") + 3.0 * variant.effect_code("SA") * variant.effect_code("HV")
    assert math.isclose(effect_coefficient(ablation_catalog, values, ("RD",)), 2.0)
    assert math.isclose(reported_factorial_effect(ablation_catalog, values, ("RD",)), 4.0)
    assert math.isclose(effect_coefficient(ablation_catalog, values, ("SA", "HV")), 3.0)
    assert math.isclose(reported_factorial_effect(ablation_catalog, values, ("SA", "HV")), 6.0)
