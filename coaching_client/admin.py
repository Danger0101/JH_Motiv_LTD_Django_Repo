from django.contrib import admin
from .models import ContentPage, ExternalLink

class ExternalLinkInline(admin.TabularInline):
    model = ExternalLink
    extra = 1

@admin.register(ContentPage)
class ContentPageAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'is_published', 'link_count', 'updated_at')
    list_filter = ('is_published', 'created_at')
    search_fields = ('title', 'content')
    prepopulated_fields = {'slug': ('title',)} # Auto-fill slug from title
    inlines = [ExternalLinkInline]
    
    @admin.display(description='Links')
    def link_count(self, obj):
        return obj.external_links.count()