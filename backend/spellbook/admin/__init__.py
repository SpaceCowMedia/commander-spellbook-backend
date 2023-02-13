from .card_admin import CardAdmin
from .template_admin import TemplateAdmin
from .feature_admin import FeatureAdmin
from .combo_admin import ComboAdmin
from .variant_admin import VariantAdmin
from .job_admin import JobAdmin
from .log_admin import LogEntryAdmin

from django.contrib import admin
admin.site.site_header = 'Spellbook Admin Panel'
admin.site.site_title = 'Spellbook Admin'
admin.site.index_title = 'Spellbook Admin Index'
