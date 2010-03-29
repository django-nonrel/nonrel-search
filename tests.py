# -*- coding: utf-8 -*-
from django.db import models
from django.test import TestCase

# use immediate_update on tests
from django.conf import settings
settings.BACKEND = 'search.backends.immediate_update'

from search.core import SearchIndexField, startswith

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
        for i in range(3):
            Indexed(one=u'OneOne%d' % i).save()

        for i in range(3):
            Indexed(one=u'one%d' % i, two='two%d' % i).save()

        for i in range(3):
            Indexed(one=(None, u'ÜÄÖ-+!#><|', 'blub')[i],
                    check=bool(i%2), value=u'value%d test-word' % i).save()

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

        self.assertEqual(len(Indexed.value_index.search('value0').filter(
            check=False)), 1)
        self.assertEqual(len(Indexed.value_index.search('value1').filter(
            check=True, one=u'ÜÄÖ-+!#><|')), 1)
        self.assertEqual(len(Indexed.value_index.search('value2').filter(
            check__exact=False, one='blub')), 1)

    def test_change(self):
        one = Indexed.one_index.search('oNeone1').get()
        one.one = 'oneoneone'
        one.save()
        # The index ListField must be empty on the main entity and filled
        # on the relation index, only
        self.assertEqual(len(Indexed.one_index.search('oNeoneo').get().one_index), 0)
        # TODO: Add _relation_index_model to the manager
#        self.assertEqual(
#            len(Indexed.one_index._relation_index_model.one_index.search('oNeoneo').get().one_index), 9)

        value = Indexed.value_index.search('value0').get()
        value.value = 'value1 test-word'
        value.save()
        value.one = 'shidori'
        value.value = 'value3 rasengan/shidori'
        value.save()
        self.assertEqual(len(Indexed.value_index.search('rasengan')), 1)
        self.assertEqual(len(Indexed.value_index.search('value3')), 1)

        value = Indexed.value_index.search('value3').get()
        value.delete()
        self.assertEqual(len(Indexed.value_index.search('value3')), 0)
