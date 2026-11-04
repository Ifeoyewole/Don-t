"""Conservative preview targets: unknown annotations are masked, never negative."""
SEWER_CODES = ('ND', 'FS', 'RB', 'DE', 'FO', 'IN', 'OB')
SEWER_MAPPING = {
    'ND': 'NORMAL', 'FS': 'JOINT_DISPLACEMENT', 'RB': 'BROKEN_PIPE',
    'DE': 'DEFORMATION', 'FO': 'OBSTACLE', 'IN': 'INFILTRATION',
    'OB': 'SURFACE_DAMAGE',
}


def sewer_targets(original_annotations, labels):
    """Return targets and observed masks only for explicitly supplied source codes."""
    targets = [0.0] * len(labels)
    observed = [0.0] * len(labels)
    for code, label in SEWER_MAPPING.items():
        if label not in labels or code not in original_annotations:
            continue
        raw = str(original_annotations[code]).strip()
        if raw not in ('0', '0.0', '1', '1.0'):
            raise ValueError(f'Invalid binary source annotation for {code}')
        index = labels.index(label)
        targets[index] = float(raw)
        observed[index] = 1.0
    return targets, observed
