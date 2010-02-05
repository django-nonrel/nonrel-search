# -*- coding: utf-8 -*-
from google.appengine.api import apiproxy_stub_map
from google.appengine.ext import db
from django.core.urlresolvers import resolve
from django.http import HttpRequest, QueryDict
from django.test import TestCase
from search.core import SearchIndexField
import base64

class Indexed(db.Model):
    # Test normal and prefix index
    one = db.StringProperty()
    two = db.StringProperty()
    one_two_index = SearchIndexField(('one', 'two'))
    check = db.BooleanProperty()

    # Test relation index
    value = db.StringProperty()
    value_index = SearchIndexField('value', integrate=('one', 'check'))

def run_tasks():
    stub = apiproxy_stub_map.apiproxy.GetStub('taskqueue')
    tasks = stub.GetTasks('default')
    for task in tasks:
        view, args, kwargs = resolve(task['url'])
        request = HttpRequest()
        request.POST = QueryDict(base64.b64decode(task['body']))
        view(request)
        stub.DeleteTask('default', task['name'])

class TestIndexed(TestCase):
    model = Indexed.value_index._relation_index_model

    def setUp(self):
        apiproxy_stub_map.apiproxy.GetStub('taskqueue').FlushQueue('default')

        for i in range(3):
            Indexed(one=u'OneOne%d' % i).put()

        for i in range(3):
            Indexed(one=u'one%d' % i, two='two%d' % i).put()

        for i in range(3):
            Indexed(one=(None, u'ÜÄÖ-+!#><|', 'blub')[i],
                    check=bool(i%2), value=u'value%d test-word' % i).put()
        run_tasks()

    def test_setup(self):
        self.assertEqual(len(Indexed.one_two_index.search('one2')), 1)
        self.assertEqual(len(Indexed.one_two_index.search('two')), 0)
        self.assertEqual(len(Indexed.one_two_index.search('two1')), 1)

        self.assertEqual(len(Indexed.value_index.search('word')), 3)
        self.assertEqual(len(Indexed.value_index.search('test-word')), 3)
        
        self.assertEqual(len(Indexed.value_index.search('value0',
            filters=('check =', False))), 1)
        self.assertEqual(len(Indexed.value_index.search('value1',
            filters=('check =', True, 'one =', u'ÜÄÖ-+!#><|'))), 1)
        self.assertEqual(len(Indexed.value_index.search('value2',
            filters=('check =', False, 'one =', 'blub'))), 1)

    def test_change(self):
        value = Indexed.value_index.search('value0').get()
        value.value = 'value1 test-word'
        value.put()
        value.one = 'shidori'
        value.value = 'value3 rasengan/shidori'
        value.put()
        run_tasks()
        self.assertEqual(len(Indexed.value_index.search('rasengan')), 1)
        self.assertEqual(len(Indexed.value_index.search('value3')), 1)

        value = Indexed.value_index.search('value3').get()
        value.delete()
        run_tasks()
        self.assertEqual(len(Indexed.value_index.search('value3')), 0)


