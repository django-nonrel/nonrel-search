# -*- coding: utf-8 -*-
from django.db import models
from django.test import TestCase
from search.core import SearchIndexField, load_backend, startswith

backend = load_backend()
update_relation_index = getattr(backend, 'update_relation_index_in_tests',
        lambda: 0)
before_test_setup = getattr(backend, 'before_test_setup', lambda: 0)

# TODO: add filters test to test if values only get indexed if the filter matches
class Indexed(models.Model):
    # Test normal and prefix index
    one = models.CharField(max_length=500, null=True)
    one_index = SearchIndexField('one', indexer=startswith)
    two = models.CharField(max_length=500)
    one_two_index = SearchIndexField(('one', 'two'))
    check = models.BooleanField()

    # Test relation index
    value = models.CharField(max_length=500)
    value_index = SearchIndexField('value', integrate=('one', 'check'))

class TestIndexed(TestCase):
    def setUp(self):
        before_test_setup()
        for i in range(3):
            Indexed(one=u'OneOne%d' % i).save()

        for i in range(3):
            Indexed(one=u'one%d' % i, two='two%d' % i).save()

        for i in range(3):
            Indexed(one=(None, u'ÜÄÖ-+!#><|', 'blub')[i],
                    check=bool(i%2), value=u'value%d test-word' % i).save()
        update_relation_index()

    def test_setup(self):
        self.assertEqual(len(Indexed.one_index.search('oneo')), 3)
        self.assertEqual(len(Indexed.one_index.search('one')), 6)

        self.assertEqual(len(Indexed.one_two_index.search('one2')), 1)
        self.assertEqual(len(Indexed.one_two_index.search('two')), 0)
        self.assertEqual(len(Indexed.one_two_index.search('two1')), 1)

        # test against empty list because a relation index is used
        self.assertEqual(Indexed.value_index.search('word').get().value_index, [])
            
        self.assertEqual(len(Indexed.value_index.search('word')), 3)
        self.assertEqual(len(Indexed.value_index.search('test-word')), 3)

        self.assertEqual(len(Indexed.value_index.search('value0',
            filters={'check':False})), 1)
        self.assertEqual(len(Indexed.value_index.search('value1',
            filters={'check':True, 'one':u'ÜÄÖ-+!#><|'})), 1)
        self.assertEqual(len(Indexed.value_index.search('value2',
            filters={'check__exact':False, 'one':'blub'})), 1)

    def test_change(self):
        one = Indexed.one_index.search('oNeone1').get()
        one.one = 'oneoneone'
        one.save()
        update_relation_index()
        # The index ListField must be empty on the main entity and filled
        # on the relation index, only
        self.assertEqual(
            len(Indexed.one_index.search('oNeoneo').get().one_index), 0)
        # TODO: Add _relation_index_model to the manager
#        self.assertEqual(
#            len(Indexed.one_index._relation_index_model.one_index.search('oNeoneo').get().one_index), 9)

        value = Indexed.value_index.search('value0').get()
        value.value = 'value1 test-word'
        value.save()
        value.one = 'shidori'
        value.value = 'value3 rasengan/shidori'
        value.save()
        update_relation_index()
        self.assertEqual(len(Indexed.value_index.search('rasengan')), 1)
        self.assertEqual(len(Indexed.value_index.search('value3')), 1)

        value = Indexed.value_index.search('value3').get()
        value.delete()
        update_relation_index()
        self.assertEqual(len(Indexed.value_index.search('value3')), 0)
