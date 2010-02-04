from django.conf import settings
from django.core.urlresolvers import reverse
from django.db import models
from django.db.models import signals
from djangotoolbox.fields import ListField
from djangotoolbox.utils import getattr_by_path
try:
    from google.appengine.api.taskqueue import Task
except:
    from google.appengine.api.labs.taskqueue import Task
from ragendja.dbutils import get_filters, transaction
from copy import copy
import re
import string
import base64
import cPickle as pickle

_PUNCTUATION_REGEX = re.compile(
    '[' + re.escape(string.punctuation.replace('-', '').replace(
        '_', '').replace('#', '')) + ']')
_PUNCTUATION_SEARCH_REGEX = re.compile(
    '[' + re.escape(string.punctuation.replace('_', '').replace(
        '#', '')) + ']')

# Various base indexers
def porter_stemmer(words, language, **kwargs):
    """Porter-stemmer in various languages."""
    languages = [language,]
    if '-' in language:
        languages.append(language.split('-')[0])

    # Fall back to English
    languages.append('en')

    # Find a stemmer for this language
    for language in languages:
        try:
            stem = __import__('search.porter_stemmers.%s' % language,
                                 {}, {}, ['']).stem
        except:
            continue
        break

    result = []
    for word in words:
        result.append(stem(word))
    return result

stop_words = {
    'en': set(('a', 'an', 'and', 'or', 'the', 'these', 'those', 'whose', 'to')),
    'de': set(('ein', 'eine', 'eines', 'einer', 'einem', 'einen', 'den',
               'der', 'die', 'das', 'dieser', 'dieses', 'diese', 'diesen',
               'deren', 'und', 'oder'))
}

def get_stop_words(language):
    if language not in stop_words and '-' in language:
        language = language.split('-', 1)[0]
    return stop_words.get(language, set())

def non_stop(words, indexing, language, **kwargs):
    """Removes stop words from search query."""
    if indexing:
        return words
    return list(set(words) - get_stop_words(language))

def porter_stemmer_non_stop(words, **kwargs):
    """Combines porter_stemmer with non_stop."""
    return porter_stemmer(non_stop(words, **kwargs), **kwargs)

# Language handler
def site_language(instance, **kwargs):
    """The default language handler tries to determine the language from
    fields in the model instance."""

    # Check if there's a language attribute
    if hasattr(instance, 'language'):
        return instance.language
    if hasattr(instance, 'lang'):
        return instance.lang

    # Does the entity have a language-specific site?
    if hasattr(instance.__class__, 'site'):
        key = instance.__class__.site.get_value_for_datastore(instance)
        if key.name() and key.name().startswith('lang:'):
            return key.name().split(':', 1)[-1]

    # Fall back to default language
    return settings.LANGUAGE_CODE

def default_splitter(text, indexing=False, **kwargs):
    """
    Returns an array of  keywords, that are included
    in query. All character besides of letters, numbers
    and '_' are split characters. The character '-' is a special 
    case: two words separated by '-' create an additional keyword
    consisting of both words without separation (see example).
    
    Examples:
    - text='word1/word2 word3'
      returns ['word1', 'word2', word3]
    - text='word1/word2-word3'
      returns ['word1', 'word2', 'word3', 'word2word3']
    """
    if not text:
        return []
    if not indexing:
        return _PUNCTUATION_SEARCH_REGEX.sub(u' ', text.lower()).split()
    keywords = []
    for word in set(_PUNCTUATION_REGEX.sub(u' ', text.lower()).split()):
        if not word:
            continue
        if '-' not in word:
            keywords.append(word)
        else:
            keywords.extend(get_word_combinations(word))
    return keywords

def get_word_combinations(word):
    """
    'one-two-three'
    =>
    ['one', 'two', 'three', 'onetwo', 'twothree', 'onetwothree']
    """
    permutations = []
    parts = [part for part in word.split(u'-') if part]
    for count in range(1, len(parts) + 1):
        for index in range(len(parts) - count + 1):
            permutations.append(u''.join(parts[index:index+count]))
    return permutations

class DictEmu(object):
    def __init__(self, data):
        self.data = data
    def __getitem__(self, key):
        return getattr(self.data, key)

class StringListField(ListField):
    def __init__(self, *args, **kwargs):
        # TODO: provide some property in the settings which tells us which
        # model field to use for field type in order to let other backends 
        # use other max_lengts,...
        self.field_type = models.CharField(max_length=500)
        super(ListField, self).__init__(*args, **kwargs)

    def contribute_to_class(self, cls, name):
        # XXX: Use contribute_to_class in order to add the model_class to the field
        super(StringListField, self).contribute_to_class(cls, name)
        self.model_class = cls

# TODO: keys_only is to app engine specific, there should be a way to refactore
# this out into the backend,
# filters should be some function in order to support django's exlude functionality,
# Q-objects, ...
class SearchableListField(StringListField):
    """
    This is basically a string ListField with search support.
    """
    def filter(self, values, filters={}, keys_only=False):
        """Returns a query for the given values (creates '=' filters for this
        property and additionally applies filters."""
        
        if not isinstance(values, (tuple, list)):
            values = (values,)
#        if keys_only:
#            filtered = self.model_class.all(keys_only=keys_only)
#        else:
#            filtered = self.model_class.all()
        filtered = self.model_class.objects.all()
        for value in set(values):
            filter = {self.name + ' =':value}
            filtered = filtered.filter(**filter)
        filtered = filtered.filter(**filters)
        return filtered

    def search(self, query, filters={},
            indexer=None, splitter=None, language=settings.LANGUAGE_CODE,
            keys_only=False):
        if not splitter:
            splitter = default_splitter
        words = splitter(query, indexing=False, language=language)
        if indexer:
            words = indexer(words, indexing=False, language=language)
        # Optimize query
        words = set(words)
        if len(words) >= 4:
            words -= get_stop_words(language)
        # Don't allow empty queries
        if not words and query:
            # This query will never find anything
            return self.filter((), filters={self.name + ' =':' '},
                               keys_only=keys_only)
        return self.filter(sorted(words), filters,
                           keys_only=keys_only)

class SearchIndexField(SearchableListField):
    """
    Simple full-text index for the given fields.

    If "relation_index" is True the index will be stored in a separate entity.

    With "integrate" you can add fields to your values/relation index,
    so they can be searched, too.

    With "filters" you can specify when a values index should be created.
    """
    default_search_queue = getattr(settings, 'DEFAULT_SEARCH_QUEUE', 'default')

    def __init__(self, fields, indexer=None, splitter=default_splitter,
            relation_index=True, integrate='*', filters={},
            language=site_language, **kwargs):
        if integrate is None:
            integrate = ()
        if integrate == '*' and not relation_index:
            integrate = ()
        if isinstance(fields, basestring):
            fields = (fields,)
        self.properties = fields
        if isinstance(integrate, basestring):
            integrate = (integrate,)
        self.filters = filters
        self.integrate = integrate
        self.splitter = splitter
        self.indexer = indexer
        self.language = language
        self.relation_index = relation_index
        if len(fields) == 0:
            raise ValueError('No fields specified for index!')
        super(SearchIndexField, self).__init__(**kwargs)

    def should_index(self, values):
        # Check if filter doesn't match
        for filter, value in get_filters(*self.filters):
            attr, op = filter.split(' ')
            op = op.lower()
            if (op == '=' and values[attr] != value or
                    op == '!=' and values[attr] == value or
                    op == 'in' and values[attr] not in value or
                    op == '<' and values[attr] >= value or
                    op == '<=' and values[attr] > value or
                    op == '>' and values[attr] <= value or
                    op == '>=' and values[attr] < value):
                return False
            elif op not in ('=', '!=', 'in', '<', '<=', '>=', '>'):
                raise ValueError('Invalid search index filter: %s %s' % (filter, value))
        return True

    @transaction
    def update_relation_index(self, parent_key, delete=False):
        model = self._relation_index_model
        
        # Generate key name (at most 250 chars)
        key_name = u'k' + unicode(parent_key.id_or_name())
        if len(key_name) > 250:
            key_name = key_name[:250]
        
        index = model.get_by_key_name(key_name, parent=parent_key)
        
        if not delete:
            parent = self.model_class.get(parent_key)
            values = None
            if parent:
                values = self.get_index_values(parent)
        
        # Remove index if it's not needed, anymore
        if delete or not self.should_index(values):
            if index:
                index.delete()
            return
        
        # Update/create index
        if not index:
            index = model(key_name=key_name, parent=parent_key, **values)

        # This guarantees that we also set virtual @properties
        for key, value in values.items():
            setattr(index, key, value)

        index.put()

    def create_index_model(self):
        attrs = dict(MODEL_NAME=self.model_class._meta.object_name,
                     PROPERTY_NAME=self.name)
        # By default we integrate everything when using relation index
        if self.relation_index and self.integrate == ('*',):
            self.integrate = tuple(property.name
                                   for property in self.model_class._meta.fields
                                   if not isinstance(property, SearchIndexField))

        for property_name in self.integrate:
            property = getattr(self.model_class, property_name)
            property = copy(property)
            attrs[property_name] = property
            if hasattr(property, 'collection_name'):
                attrs[property_name].collection_name = '_sidx_%s_%s_set_' % (
                    self.model_class._meta.object_name.lower(),
                    self.name,
                )
        index_name = self.name
        attrs[index_name] = SearchIndexField(self.properties,
            splitter=self.splitter, indexer=self.indexer,
            language=self.language, relation_index=False)
        if self.relation_index:
            owner = self
            def __init__(self, parent, *args, **kwargs):
                # Save some space: don't copy the whole indexed text into the
                # relation index property unless the property gets integrated.
                for key, value in kwargs.items():
                    if key in self.properties() or \
                            key not in owner.model_class.properties():
                        continue
                    setattr(self, key, value)
                    del kwargs[key]
                db.Model.__init__(self, parent=parent, *args, **kwargs)
            attrs['__init__'] = __init__
            self._relation_index_model = type(
                'RelationIndex__%s_%s__%s' % (self.model_class._meta.app_label,
                                           self.model_class._meta.object_name,
                                           self.name),
                (db.Model,), attrs)

    def get_index_values(self, model_instance):
        filters = tuple([f[0].split(' ')[0]
                         for f in get_filters(*self.filters)])
        values = {}
        for property in set(self.properties + self.integrate + filters):
            instance = getattr(model_instance.__class__, property)
            if isinstance(instance, db.ReferenceProperty):
                value = instance.get_value_for_datastore(model_instance)
            else:
                value = getattr(model_instance, property)
            if property == self.properties[0] and \
                    isinstance(value, (list, tuple)):
                value = sorted(value)
            values[property] = value
        return values

    def get_value_for_datastore(self, model_instance):
        if self.filters and not self.should_index(DictEmu(model_instance)) \
                or self.relation_index:
            return []
        
        language = self.language
        if callable(language):
            language = language(model_instance, property=self)
        
        index = []
        for property in self.properties:
            values = getattr_by_path(model_instance, property, None)
            if not values:
                values = ()
            elif not isinstance(values, (list, tuple)):
                values = (values,)
            for value in values:
                index.extend(self.splitter(value, indexing=True, language=language))
        if self.indexer:
            index = self.indexer(index, indexing=True, language=language)
        # Sort index to make debugging easier
        setattr(model_instance, self.name, sorted(set(index)))
        return index

    def make_value_from_datastore(self, value):
        return value

    def search(self, query, filters={},
               language=settings.LANGUAGE_CODE, keys_only=False):
        if self.relation_index:
            items = getattr(self._relation_index_model, self.name).search(query,
                filters, language=language,
                keys_only=True)
            return RelationIndexQuery(self, items, keys_only=keys_only)
        return super(SearchIndexField, self).search(query, filters,
            splitter=self.splitter,
            indexer=self.indexer, language=language, keys_only=keys_only)

def push_update_relation_index(model_descriptor, property_name, parent_key,
        delete):
    Task(url=reverse('search.views.update_relation_index'),  method='POST',
        params={
            'property_name': property_name,
            'model_descriptor': base64.b64encode(pickle.dumps(model_descriptor)),
            'parent_key':base64.b64encode(pickle.dumps(parent_key)),
            'delete':base64.b64encode(pickle.dumps(delete)),
        }).add(SearchIndexField.default_search_queue)

def post(delete, sender, instance, **kwargs):
    for property in sender._meta.fields:
        if isinstance(property, SearchIndexField):
            if property.relation_index:
                if delete:
                    parent_key = instance._rel_idx_key_
                else:
                  parent_key = instance.key()
                push_update_relation_index([sender._meta.app_label,
                    sender._meta.object_name], property.name, parent_key, delete)

def pre_delete(sender, instance, **kwargs):
    instance._rel_idx_key_ = instance.key()

def post_save_committed(sender, instance, **kwargs):
    # Update indexes after transaction
    post(False, sender, instance, **kwargs)

def post_delete_committed(sender, instance, **kwargs):
    # Update indexes after transaction
    post(True, sender, instance, **kwargs)

def install_index_model(sender, **kwargs):
    needs_relation_index = False
    for property in sender._meta.fields:
        if isinstance(property, SearchIndexField) and property.relation_index:
            property.create_index_model()
            needs_relation_index = True
    if needs_relation_index:
        signals.post_save_committed.connect(post_save_committed, sender=sender)
        signals.pre_delete.connect(pre_delete, sender=sender)
        signals.post_delete_committed.connect(post_delete_committed, sender=sender)
signals.class_prepared.connect(install_index_model)

class QueryTraits(object):
    def __iter__(self):
        return iter(self[:301])

    def __len__(self):
        return self.count()

    def get(self):
        result = self[:1]
        if result:
            return result[0]
        return None

    def fetch(self, limit=301):
        return self[:limit]

class RelationIndexQuery(QueryTraits):
    """Combines the results of multiple queries by appending the queries in the
    given order."""
    def __init__(self, property, query, keys_only):
        self.model = property.model_class
        self.property = property
        self.query = query
        self.keys_only = keys_only

    def order(self, *args, **kwargs):
        self.query = self.query.order(*args, **kwargs)

    def filter(self, *args, **kwargs):
        self.query = self.query.filter(*args, **kwargs)

    def __getitem__(self, index):
        keys = [key.parent() for key in self.query[index]]
        if self.keys_only:
            return keys
        return [item for item in self.model.get(keys) if item]

    def count(self, max=301):
        return self.query.count(max)
