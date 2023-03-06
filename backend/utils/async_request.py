import aiohttp
#import json_logging


def AsyncRequest(headers=None):
    # corr_id = {"X-Correlation-ID": json_logging.get_correlation_id()}
    # headers = {**headers, **corr_id} if headers else corr_id
    return aiohttp.ClientSession(headers=headers)
