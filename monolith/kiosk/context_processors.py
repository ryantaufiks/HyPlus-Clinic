from django.conf import settings


def app_settings(request):
    """Settings the browser-side code needs, e.g. to show times in the clinic's zone."""
    return {"app_time_zone": settings.TIME_ZONE}
