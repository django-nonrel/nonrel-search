from django.conf import settings
from django.db import models
from google.appengine.ext import deferred

default_search_queue = getattr(settings, 'DEFAULT_SEARCH_QUEUE', 'default')

def update_relation_index(search_index_field, parent_pk, delete):
    # pass only the field / model names to the background task to transfer less
    # data
    app_label = search_index_field.model_class._meta.app_label
    object_name = search_index_field.model_class._meta.object_name
    deferred.defer(update, app_label, object_name, search_index_field.name,
        parent_pk, delete, _queue=default_search_queue)

def update(app_label, object_name, field_name, parent_pk, delete):
    model = models.get_model(app_label, object_name)
    update_property = model._meta.get_field_by_name(field_name)[0]
    update_property.update_relation_index(parent_pk, delete)