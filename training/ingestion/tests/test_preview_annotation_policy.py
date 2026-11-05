from training.preview_annotation_policy import sewer_targets


def test_missing_infiltration_annotation_is_unknown():
    target, mask = sewer_targets({'FS': '1'}, ['JOINT_DISPLACEMENT', 'INFILTRATION'])
    assert target == [1.0, 0.0]
    assert mask == [1.0, 0.0]


def test_explicit_infiltration_negative_is_observed():
    target, mask = sewer_targets({'IN': '0'}, ['INFILTRATION'])
    assert target == [0.0]
    assert mask == [1.0]


def test_deposits_and_branches_do_not_invent_damage_or_lateral_labels():
    target, mask = sewer_targets({'AF': '1', 'BE': '1', 'GR': '1', 'PB': '1'},
                                 ['SURFACE_DAMAGE', 'PROTRUDING_LATERAL'])
    assert target == [0.0, 0.0]
    assert mask == [0.0, 0.0]


def test_obstacle_does_not_establish_unreliable_geometry():
    target, mask = sewer_targets({'FO': '1'}, ['OBSTACLE', 'GEOMETRY_UNCERTAIN'])
    assert target == [1.0, 0.0]
    assert mask == [1.0, 0.0]
