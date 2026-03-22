import math
from datetime import timedelta


RATE_MAP = {
    'HOURLY': 50.0,
    'DAILY': 500.0,
    'MONTHLY': 10000.0,
}


def calculate_units(reservation_type, start_time, end_time):
    duration = end_time - start_time
    if duration <= timedelta(0):
        return 0

    total_hours = duration.total_seconds() / 3600

    if reservation_type == 'MONTHLY':
        return max(1, math.ceil(total_hours / (24 * 30)))
    if reservation_type == 'DAILY':
        return max(1, math.ceil(total_hours / 24))
    return max(1, math.ceil(total_hours))


def calculate_reservation_amount(reservation_type, start_time, end_time):
    rate = RATE_MAP.get(reservation_type, RATE_MAP['HOURLY'])
    units = calculate_units(reservation_type, start_time, end_time)
    return round(rate * units, 2)


def get_rate_label(reservation_type):
    if reservation_type == 'MONTHLY':
        return '/month'
    if reservation_type == 'DAILY':
        return '/day'
    return '/hr'


def calculate_commission_split(amount, owner_percent):
    owner_percent = max(0.0, min(float(owner_percent), 100.0))
    gross_amount = round(float(amount), 2)
    owner_earning = round(gross_amount * (owner_percent / 100.0), 2)
    platform_fee = round(gross_amount - owner_earning, 2)
    return owner_earning, platform_fee