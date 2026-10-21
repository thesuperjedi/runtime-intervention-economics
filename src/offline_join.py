"""Offline pairing helper extracted from original validator; no execution imports."""
def paired_strong_run_id(source_cheap_run_id):
    if '-cheap-' not in source_cheap_run_id:
        raise ValueError('source must be a cheap solver observation')
    return source_cheap_run_id.replace('-cheap-', '-strong-', 1)
