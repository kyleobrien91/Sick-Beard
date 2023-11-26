from datetime import tzinfo, timedelta

class TimezoneUTC(tzinfo):
    """UTC timezone"""
    ZERO = timedelta(0)

    def utcoffset(self, dt):
        return TimezoneUTC.ZERO

    def tzname(self, dt):
        return u"UTC"

    def dst(self, dt):
        return TimezoneUTC.ZERO

    def __repr__(self):
        return "<TimezoneUTC delta=0, name=u'UTC'>"

class Timezone(TimezoneUTC):
    """Fixed offset in hour from UTC."""
    def __init__(self, offset):
        self._offset = timedelta(minutes=offset*60)
        self._name = u"%+03u00" % offset

    def utcoffset(self, dt):
        return self._offset

    def tzname(self, dt):
        return self._name

    def __repr__(self):
        return f"<Timezone delta={self._offset}, name='{self._name}'>"

UTC = TimezoneUTC()

def createTimezone(offset):
    return Timezone(offset) if offset else UTC

