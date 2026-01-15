from django.contrib import admin
from .models import FunnelTier, TierPerk


class TierPerkInline(admin.TabularInline):
    model = TierPerk
    fields = ('text', 'link_url', 'linked_offering', 'order')
    autocomplete_fields = ('linked_offering',)
    extra = 1


@admin.register(FunnelTier)
class FunnelTierAdmin(admin.ModelAdmin):
    list_display = ('name', 'quantity', 'variant', 'total_price', 'order', 'is_active')
    list_editable = ('order', 'is_active')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [TierPerkInline]
