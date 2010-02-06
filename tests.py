# -*- coding: utf-8 -*-
from google.appengine.api import apiproxy_stub_map
from django.db import models
from django.core.urlresolvers import resolve
from django.http import HttpRequest, QueryDict
from django.test import TestCase
from search.core import SearchIndexField
import base64

class Indexed(models.Model):
    # Test normal and prefix index
    one = models.CharField(max_length=500, null=True)
    two = models.CharField(max_length=500)
    one_two_index = SearchIndexField(('one', 'two'))
    check = models.BooleanField()

    # Test relation index
    value = models.CharField(max_length=500)
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
    model = Indexed._meta.get_field_by_name('value_index')[0]._relation_index_model

    def setUp(self):
        apiproxy_stub_map.apiproxy.GetStub('taskqueue').FlushQueue('default')

        for i in range(3):
            Indexed(one=u'OneOne%d' % i).save()

        for i in range(3):
            Indexed(one=u'one%d' % i, two='two%d' % i).save()

        for i in range(3):
            Indexed(one=(None, u'ÜÄÖ-+!#><|', 'blub')[i],
                    check=bool(i%2), value=u'value%d test-word' % i).save()
        run_tasks()

    def test_setup(self):
        value_index = Indexed._meta.get_field_by_name('value_index')[0]
        one_two_index = value_index = Indexed._meta.get_field_by_name(
            'one_two_index')[0]
        self.assertEqual(len(one_two_index.search('one2')), 1)
        self.assertEqual(len(one_two_index.search('two')), 0)
        self.assertEqual(len(one_two_index.search('two1')), 1)

        self.assertEqual(len(value_index.search('word')), 3)
        self.assertEqual(len(value_index.search('test-word')), 3)

        self.assertEqual(len(value_index.search('value0',
            filters={'check':False})), 1)
        self.assertEqual(len(value_index.search('value1',
            filters={'check':True, 'one':u'ÜÄÖ-+!#><|'})), 1)
        self.assertEqual(len(value_index.search('value2',
            filters={'check__exact':False, 'one':'blub'})), 1)

    def test_change(self):
        index = Indexed._meta.get_field_by_name('value_index')[0]
        value = index.search('value0').get()
        value.value = 'value1 test-word'
        value.save()
        value.one = 'shidori'
        value.value = 'value3 rasengan/shidori'
        value.save()
        run_tasks()
        self.assertEqual(len(index.search('rasengan')), 1)
        self.assertEqual(len(index.search('value3')), 1)

        value = index.search('value3').get()
        value.delete()
        run_tasks()
        self.assertEqual(len(index.search('value3')), 0)
