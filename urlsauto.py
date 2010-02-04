from django.conf.urls.defaults import *

rootpatterns = patterns('search.views',
    (r'^bg-tasks/search/update_relation_index/$', 'update_relation_index'),
)
