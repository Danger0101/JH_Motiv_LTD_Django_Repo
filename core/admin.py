from django.contrib import admin

# Register your models here.

# --- GLOBAL CONFIGURATION ---
# Place this in core/admin.py (or any main admin.py file loaded at startup)

admin.site.site_header = "JH Motiv Operations"       # Top of every admin page
admin.site.site_title = "JH Motiv Admin"             # Browser tab title
admin.site.index_title = "Business Dashboard"        # Main index page title
admin.site.empty_value_display = "-empty-"           # Replaces "(None)" in lists for cleaner reading

# Optional: Disable the default "Groups" model if you don't use complex permissions
# from django.contrib.auth.models import Group
# admin.site.unregister(Group)
