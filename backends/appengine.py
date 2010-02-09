from django.conf import settings
from django.core.urlresolvers import reverse
try:
    from google.appengine.api.taskqueue import Task
except:
    from google.appengine.api.labs.taskqueue import Task
import base64
import cPickle as pickle

default_search_queue = getattr(settings, 'DEFAULT_SEARCH_QUEUE', 'default')
# TODO: use defered library
def update_relation_index(model_descriptor, property_name, parent_key,
        delete):
    # TODO: Let the backend install urls somehow
    Task(url=reverse('search.views.update_relation_index'),  method='POST',
        params={
            'property_name': property_name,
            'model_descriptor': base64.b64encode(pickle.dumps(model_descriptor)),
            'parent_key':base64.b64encode(pickle.dumps(parent_key)),
            'delete':base64.b64encode(pickle.dumps(delete)),
        }).add(default_search_queue)