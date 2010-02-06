from django.conf.urls.defaults import *

urlpatterns = patterns('search.views',
    (r'^bg-tasks/search/update_relation_index/$', 'update_relation_index'),
)
