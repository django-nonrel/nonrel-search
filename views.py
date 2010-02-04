# -*- coding: utf-8 -*-
from appenginepatcher import on_production_server
from django.db import models
from django.http import HttpResponse
from google.appengine.api import users
import base64
import cPickle as pickle

def update_relation_index(request):
    if 'property_name' in request.POST and 'model_descriptor' in request.POST \
          and 'parent_key' in request.POST and 'delete' in request.POST:
        model_descriptor = pickle.loads(base64.b64decode(request.POST[
            'model_descriptor']))
        model = models.get_model(model_descriptor[0], model_descriptor[1])
        update_property = getattr(model, request.POST['property_name'])
        parent_key = pickle.loads(base64.b64decode(request.POST['parent_key']))
        delete = pickle.loads(base64.b64decode(request.POST['delete']))
        update_property.update_relation_index(parent_key, delete)
    return HttpResponse()
