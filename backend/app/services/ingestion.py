"""Load raw NASA data (CSV / PDF / NTRS reports / PSI datasets) -> cleaned records in data/processed."""


def load_raw_files():
    # TODO: parse CSV/JSON datasets and PDF reports from data/raw
    raise NotImplementedError


def clean_and_normalize(records):
    # TODO: unit normalization (kPa, %O2, cm/s), dedupe, missing values
    raise NotImplementedError
