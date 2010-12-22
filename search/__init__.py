from search.core import default_splitter, site_language, SearchManager, \
    install_index_model

def autodiscover():
    """
    Automatically add managers from search_indexes modules.
    """
    import imp
    from django.conf import settings
    from django.utils.importlib import import_module

    for app in settings.INSTALLED_APPS:
        # For each app, we need to look for an search_indexes.py inside that app's
        # package. We can't use os.path here -- recall that modules may be
        # imported different ways (think zip files) -- so we need to get
        # the app's __path__ and look for search_indexes.py on that path.

        # Step 1: find out the app's __path__ Import errors here will (and
        # should) bubble up, but a missing __path__ (which is legal, but weird)
        # fails silently -- apps that do weird things with __path__ might
        # need to roll their own index registration.
        try:
            app_path = import_module(app).__path__
        except AttributeError:
            continue

        # Step 2: use imp.find_module to find the app's search_indexes.py. For some
        # reason imp.find_module raises ImportError if the app can't be found
        # but doesn't actually try to import the module. So skip this app if
        # its search_indexes.py doesn't exist
        try:
            imp.find_module('search_indexes', app_path)
        except ImportError:
            continue

        # Step 3: import the app's search_index file. If this has errors we want them
        # to bubble up.
        import_module("%s.search_indexes" % app)

def register(model, fields_to_index, search_index='search_index',
    indexer=None, splitter=default_splitter, relation_index=True, integrate='*',
    filters={}, language=site_language, **kwargs):

    """
    Add a search manager to the model.
    """

    if not hasattr(model, '_meta'):
        raise AttributeError('The model being registered must derive from Model.')

    if hasattr(model, search_index):
        raise AttributeError('The model being registered already defines a'
            ' property called %s.' % search_index)

    model.add_to_class(search_index, SearchManager(fields_to_index, indexer,
        splitter, relation_index, integrate, filters, language, **kwargs))

    install_index_model(model)
