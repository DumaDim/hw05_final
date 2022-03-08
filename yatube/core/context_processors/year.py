import datetime


def year(request):
    datetime_object = datetime.datetime.now()
    return {'year': datetime_object.year}
