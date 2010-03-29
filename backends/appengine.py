from django.conf import settings
from django.core.urlresolvers import resolve
from django.http import HttpRequest, QueryDict
from google.appengine.api import apiproxy_stub_map
from google.appengine.ext import deferred
import base64
from search.views import update_relation_index as update

default_search_queue = getattr(settings, 'DEFAULT_SEARCH_QUEUE', 'default')
def update_relation_index(model_descriptor, property_name, parent_key,
        delete):
    deferred.defer(update, property_name, model_descriptor, parent_key, delete,
        _queue=default_search_queue)

def update_relation_index_in_tests():
    stub = apiproxy_stub_map.apiproxy.GetStub('taskqueue')
    tasks = stub.GetTasks(default_search_queue)
    for task in tasks:
        view, args, kwargs = resolve(task['url'])
        request = HttpRequest()
        request.POST = QueryDict(base64.b64decode(task['body']))
        view(request)
        stub.DeleteTask(default_search_queue, task['name'])

def before_test_setup():
    apiproxy_stub_map.apiproxy.GetStub('taskqueue').FlushQueue(default_search_queue)